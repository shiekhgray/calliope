#!/usr/bin/env python3
"""
Library scanner for Calliope.

Walks the music directory and upserts artists, albums, tracks, and genres
into the database. Safe to run repeatedly — fully idempotent.

Run from inside the API container:
    python scripts/scan.py

Or via Docker Compose:
    docker compose exec api python scripts/scan.py
"""

import fnmatch
import os
import sys
from pathlib import Path

# Ensure /app is on the path so `app.*` imports resolve inside the container
sys.path.insert(0, str(Path(__file__).parent.parent))

from mutagen import File as MutagenFile
from mutagen.id3 import ID3NoHeaderError
from sqlalchemy.orm import Session

from app.config import settings
from app.database import engine
from app import models

AUDIO_EXTENSIONS = {".mp3", ".m4a", ".wav"}
IGNORED_NAMES = {"desktop.ini", ".ds_store", "thumbs.db"}

# Optional per-album marker dropped by importers (e.g. qobuz_import.py --loose)
# to seed album_type. Applied only when the album is first created — never
# overrides a later manual change via PATCH /albums/{id}/type.
ALBUM_TYPE_MARKER = ".album_type"
VALID_ALBUM_TYPES = {"album", "ep", "single"}


# ---------------------------------------------------------------------------
# Cover art resolution
# ---------------------------------------------------------------------------

def find_cover_art(album_dir: Path, music_root: Path) -> str | None:
    """Return relative path (from music_root) to cover art, or None."""
    candidates = list(album_dir.iterdir()) if album_dir.is_dir() else []
    jpg_files = [f for f in candidates if f.suffix.lower() == ".jpg"]

    # Priority 1: Folder.jpg (case-insensitive)
    for f in jpg_files:
        if f.name.lower() == "folder.jpg":
            return str(f.relative_to(music_root))

    # Priority 2: AlbumArt*_Large.jpg
    for f in jpg_files:
        if fnmatch.fnmatch(f.name.lower(), "albumart*_large.jpg"):
            return str(f.relative_to(music_root))

    # Priority 3: first .jpg found
    if jpg_files:
        return str(sorted(jpg_files)[0].relative_to(music_root))

    return None


def read_album_type(album_dir: Path) -> str | None:
    """Return the album_type from a `.album_type` marker file, or None if absent/invalid."""
    marker = album_dir / ALBUM_TYPE_MARKER
    if not marker.is_file():
        return None
    value = marker.read_text(encoding="utf-8").strip().lower()
    return value if value in VALID_ALBUM_TYPES else None


# ---------------------------------------------------------------------------
# Tag extraction
# ---------------------------------------------------------------------------

def read_tags(path: Path) -> dict:
    """Extract relevant tags from an audio file using Mutagen."""
    result = {
        "title": path.stem,
        "artist": None,
        "albumartist": None,
        "album": None,
        "track_number": None,
        "year": None,
        "genres": [],
        "duration_ms": None,
        "bitrate_kbps": None,
    }

    try:
        audio = MutagenFile(path, easy=True)
    except Exception:
        return result

    if audio is None:
        return result

    # Duration and bitrate
    if audio.info:
        if hasattr(audio.info, "length"):
            result["duration_ms"] = int(audio.info.length * 1000)
        if hasattr(audio.info, "bitrate") and audio.info.bitrate:
            result["bitrate_kbps"] = int(audio.info.bitrate / 1000)

    def first(tag):
        val = audio.tags.get(tag) if audio.tags else None
        return val[0] if val else None

    ext = path.suffix.lower()

    if ext in (".mp3", ".wav"):
        result["title"] = first("title") or path.stem
        result["artist"] = first("artist")
        result["albumartist"] = first("albumartist")
        result["album"] = first("album")
        result["year"] = _parse_year(first("date"))
        result["genres"] = _parse_list(audio.tags, "genre") if audio.tags else []
        raw_track = first("tracknumber")
        result["track_number"] = _parse_track_number(raw_track)

    elif ext == ".m4a":
        result["title"] = first("title") or path.stem
        result["artist"] = first("artist")
        result["albumartist"] = first("aART")
        result["album"] = first("album")
        result["year"] = _parse_year(first("date"))
        result["genres"] = _parse_list(audio.tags, "genre") if audio.tags else []
        raw_track = first("tracknumber")
        result["track_number"] = _parse_track_number(str(raw_track) if raw_track else None)

    return result


def _parse_year(value: str | None) -> int | None:
    if not value:
        return None
    try:
        return int(str(value)[:4])
    except ValueError:
        return None


def _parse_track_number(value: str | None) -> int | None:
    if not value:
        return None
    try:
        return int(str(value).split("/")[0])
    except ValueError:
        return None


def _parse_list(tags, key: str) -> list[str]:
    val = tags.get(key)
    if not val:
        return []
    if isinstance(val, list):
        return [str(v).strip() for v in val if v]
    return [str(val).strip()]


# ---------------------------------------------------------------------------
# Database upsert helpers
# ---------------------------------------------------------------------------

def upsert_artist(db: Session, name: str) -> models.Artist:
    artist = db.query(models.Artist).filter_by(name=name).first()
    if not artist:
        artist = models.Artist(name=name)
        db.add(artist)
        db.flush()
    return artist


def upsert_album(
    db: Session,
    artist: models.Artist,
    title: str,
    year: int | None,
    cover_art_path: str | None,
    album_type: str | None = None,
) -> models.Album:
    album = db.query(models.Album).filter_by(artist_id=artist.id, title=title).first()
    if not album:
        album = models.Album(
            artist_id=artist.id,
            title=title,
            year=year,
            cover_art_path=cover_art_path,
        )
        # Seed album_type from importer marker on creation only; rescans must
        # not clobber a later manual change via PATCH /albums/{id}/type.
        if album_type:
            album.album_type = album_type
        db.add(album)
        db.flush()
    else:
        # Update year and cover art if we now have values we didn't before
        if year and not album.year:
            album.year = year
        if cover_art_path and not album.cover_art_path:
            album.cover_art_path = cover_art_path

    # Ensure album_artists row exists (idempotent — new albums won't have one yet)
    exists = db.query(models.AlbumArtist).filter_by(
        album_id=album.id, artist_id=artist.id
    ).first()
    if not exists:
        db.add(models.AlbumArtist(album_id=album.id, artist_id=artist.id))

    return album


def upsert_track(
    db: Session,
    album: models.Album,
    tags: dict,
    file_path_rel: str,
    fmt: str,
) -> models.Track:
    track = db.query(models.Track).filter_by(file_path=file_path_rel).first()
    if not track:
        track = models.Track(
            album_id=album.id,
            title=tags["title"],
            track_number=tags["track_number"],
            duration_ms=tags["duration_ms"],
            bitrate_kbps=tags["bitrate_kbps"],
            file_path=file_path_rel,
            format=fmt,
        )
        db.add(track)
        db.flush()
    else:
        track.album_id = album.id
        track.title = tags["title"]
        track.track_number = tags["track_number"]
        track.duration_ms = tags["duration_ms"]
        track.bitrate_kbps = tags["bitrate_kbps"]
    return track


def upsert_genres(db: Session, track: models.Track, genre_names: list[str]):
    if not genre_names:
        return
    existing_genre_ids = {g.id for g in track.genres}

    for name in genre_names:
        name = name.strip()
        if not name:
            continue
        genre = db.query(models.Genre).filter_by(name=name).first()
        if not genre:
            genre = models.Genre(name=name)
            db.add(genre)
            db.flush()
        if genre.id not in existing_genre_ids:
            db.add(models.TrackGenre(track_id=track.id, genre_id=genre.id))
            existing_genre_ids.add(genre.id)


# ---------------------------------------------------------------------------
# Main scan
# ---------------------------------------------------------------------------

def scan(music_root: Path):
    print(f"Scanning: {music_root}")

    counts = {"artists": 0, "albums": 0, "tracks": 0, "skipped": 0}

    with Session(engine) as db:
        # Walk Artist/Album/Track structure
        for artist_dir in sorted(music_root.iterdir()):
            if not artist_dir.is_dir():
                continue

            artist_name = artist_dir.name
            artist_obj = None  # lazy — only create if we find audio

            for album_dir in sorted(artist_dir.iterdir()):
                if not album_dir.is_dir():
                    continue

                album_title = album_dir.name
                cover_art = find_cover_art(album_dir, music_root)
                marker_album_type = read_album_type(album_dir)
                album_obj = None  # lazy
                artist_obj = None  # reset per album so albumartist tag is re-evaluated

                for track_file in sorted(album_dir.iterdir()):
                    if track_file.name.lower() in IGNORED_NAMES:
                        continue
                    if track_file.suffix.lower() not in AUDIO_EXTENSIONS:
                        continue
                    if not track_file.is_file():
                        continue

                    tags = read_tags(track_file)
                    fmt = track_file.suffix.lstrip(".").lower()
                    file_path_rel = str(track_file.relative_to(music_root))

                    # albumartist tag takes priority for album ownership (compilations)
                    effective_artist = tags["albumartist"] or tags["artist"] or artist_name
                    effective_album = tags["album"] or album_title

                    if artist_obj is None:
                        artist_obj = upsert_artist(db, effective_artist)
                        counts["artists"] += 1

                    if album_obj is None:
                        album_obj = upsert_album(
                            db, artist_obj, effective_album, tags["year"], cover_art,
                            album_type=marker_album_type,
                        )
                        counts["albums"] += 1

                    track_obj = upsert_track(db, album_obj, tags, file_path_rel, fmt)
                    upsert_genres(db, track_obj, tags["genres"])
                    counts["tracks"] += 1

                    if counts["tracks"] % 100 == 0:
                        print(f"  {counts['tracks']} tracks processed...")
                        db.flush()

        db.commit()

    print(
        f"\nDone. "
        f"{counts['artists']} artists, "
        f"{counts['albums']} albums, "
        f"{counts['tracks']} tracks."
    )


if __name__ == "__main__":
    music_root = Path(settings.music_root)
    if not music_root.exists():
        print(f"ERROR: Music root not found: {music_root}", file=sys.stderr)
        sys.exit(1)
    scan(music_root)
