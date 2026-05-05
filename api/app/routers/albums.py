import json
import logging
import mimetypes
import os
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path

import numpy as np
from fastapi import APIRouter, Body, Depends, HTTPException, Query, UploadFile
from fastapi.responses import FileResponse
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.config import settings
from app.database import get_db
from app import models
from app.auth import get_current_user

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/albums", tags=["albums"])


@router.get("/{album_id}")
def get_album(album_id: int, db: Session = Depends(get_db)):
    album = db.get(models.Album, album_id)
    if not album:
        raise HTTPException(status_code=404)

    # Fetch all track credits for this album in one query
    credit_rows = db.execute(text("""
        SELECT tc.track_id, tc.artist_id, ar.name AS artist_name
        FROM track_credits tc
        JOIN artists ar ON ar.id = tc.artist_id
        WHERE tc.track_id IN (
            SELECT id FROM tracks WHERE album_id = :album_id
        )
    """), {"album_id": album_id}).fetchall()

    credits_by_track: dict[int, list[dict]] = {}
    for row in credit_rows:
        credits_by_track.setdefault(row.track_id, []).append(
            {"artist_id": row.artist_id, "artist_name": row.artist_name}
        )

    return {
        "id": album.id,
        "title": album.title,
        "year": album.year,
        "cover_art_path": album.cover_art_path,
        "album_type": album.album_type,
        "artist_id": album.artist_id,
        "artist_name": album.artist.name,
        "tracks": [
            {
                "id": t.id,
                "title": t.title,
                "track_number": t.track_number,
                "duration_ms": t.duration_ms,
                "bitrate_kbps": t.bitrate_kbps,
                "format": t.format,
                "play_count": t.play_count,
                "credits": credits_by_track.get(t.id, []),
            }
            for t in album.tracks
        ],
    }


@router.put("/{album_id}/art")
async def upload_album_art(
    album_id: int,
    file: UploadFile,
    db: Session = Depends(get_db),
    _user=Depends(get_current_user),
):
    album = db.get(models.Album, album_id)
    if not album:
        raise HTTPException(status_code=404)

    if not file.content_type or not file.content_type.startswith("image/"):
        raise HTTPException(status_code=422, detail="File must be an image")

    # Derive album directory from the first track
    if not album.tracks:
        raise HTTPException(status_code=422, detail="Album has no tracks — cannot determine directory")

    album_dir = Path(settings.music_root) / Path(album.tracks[0].file_path).parent
    dest = album_dir / "Folder.jpg"

    content = await file.read()
    dest.write_bytes(content)

    rel_path = str(Path(album.tracks[0].file_path).parent / "Folder.jpg")
    album.cover_art_path = rel_path
    db.commit()

    return {"cover_art_path": rel_path}


_VALID_ALBUM_TYPES = {"album", "ep", "single"}


@router.patch("/{album_id}/type")
def set_album_type(
    album_id: int,
    album_type: str = Body(..., embed=True),
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user),
):
    if current_user.id != 1:
        raise HTTPException(status_code=403, detail="Owner only")
    if album_type not in _VALID_ALBUM_TYPES:
        raise HTTPException(status_code=400, detail="album_type must be 'album', 'ep', or 'single'")
    album = db.get(models.Album, album_id)
    if not album:
        raise HTTPException(status_code=404)
    album.album_type = album_type
    db.commit()
    db.refresh(album)
    return {
        "id": album.id,
        "title": album.title,
        "year": album.year,
        "cover_art_path": album.cover_art_path,
        "album_type": album.album_type,
        "artist_id": album.artist_id,
        "artist_name": album.artist.name,
    }


@router.get("/{album_id}/art")
def get_album_art(album_id: int, db: Session = Depends(get_db)):
    album = db.get(models.Album, album_id)
    if not album or not album.cover_art_path:
        raise HTTPException(status_code=404)

    art_path = Path(settings.music_root) / album.cover_art_path
    if not art_path.is_file():
        raise HTTPException(status_code=404)

    media_type = mimetypes.guess_type(str(art_path))[0] or "image/jpeg"
    return FileResponse(
        str(art_path),
        media_type=media_type,
        headers={"Cache-Control": "public, max-age=31536000, immutable"},
    )


# ---------------------------------------------------------------------------
# Genre endpoints
# ---------------------------------------------------------------------------

def _get_album_or_404(album_id: int, db: Session) -> models.Album:
    album = db.get(models.Album, album_id)
    if not album:
        raise HTTPException(status_code=404, detail="Album not found")
    return album


def _existing_genre_names(album_id: int, db: Session) -> set[str]:
    """Return the set of genre names already applied to any track in this album."""
    rows = db.execute(text("""
        SELECT DISTINCT g.name
        FROM genres g
        JOIN track_genres tg ON tg.genre_id = g.id
        JOIN tracks t ON t.id = tg.track_id
        WHERE t.album_id = :album_id
    """), {"album_id": album_id}).fetchall()
    return {row.name for row in rows}


def _fetch_lastfm(url: str) -> dict | None:
    """Fire a Last.fm API request. Returns parsed JSON or None on failure."""
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "Calliope/2.0"})
        with urllib.request.urlopen(req, timeout=10) as resp:
            return json.loads(resp.read())
    except Exception as exc:
        logger.warning("Last.fm request failed: %s", exc)
        return None


@router.get("/{album_id}/genres")
def get_album_genres(album_id: int, db: Session = Depends(get_db)):
    """Return distinct genres currently applied to the album."""
    _get_album_or_404(album_id, db)
    rows = db.execute(text("""
        SELECT DISTINCT g.id, g.name
        FROM genres g
        JOIN track_genres tg ON tg.genre_id = g.id
        JOIN tracks t ON t.id = tg.track_id
        WHERE t.album_id = :album_id
        ORDER BY g.name
    """), {"album_id": album_id}).fetchall()
    return [{"id": row.id, "name": row.name} for row in rows]


@router.get("/{album_id}/genres/fetch")
def fetch_album_genres_lastfm(album_id: int, db: Session = Depends(get_db)):
    """Fetch genre suggestions from Last.fm album.getInfo."""
    album = _get_album_or_404(album_id, db)

    if not settings.lastfm_api_key:
        return []

    artist_name = album.artist.name
    album_title = album.title

    encoded_artist = urllib.parse.quote(artist_name)
    encoded_album = urllib.parse.quote(album_title)
    url = (
        f"http://ws.audioscrobbler.com/2.0/"
        f"?method=album.getInfo"
        f"&api_key={settings.lastfm_api_key}"
        f"&artist={encoded_artist}"
        f"&album={encoded_album}"
        f"&format=json"
    )

    data = _fetch_lastfm(url)
    if not data:
        return []

    tags = (data.get("album") or {}).get("toptags", {}).get("tag", [])
    if not isinstance(tags, list):
        return []

    existing = _existing_genre_names(album_id, db)

    suggestions = []
    for tag in tags:
        name = tag.get("name", "").strip().lower()
        weight = int(tag.get("count", 0))
        if not name or weight < 10:
            continue
        if name in existing:
            continue
        suggestions.append({"name": name, "source": "lastfm", "weight": weight})
        if len(suggestions) >= 5:
            break

    return suggestions


DIM_SLICES = {
    "timbre":            slice(0, 13),
    "timbral_variation": slice(13, 26),
    "harmony":           slice(26, 38),
    "chord_movement":    slice(38, 50),
    "tempo":             slice(50, 51),
    "loudness":          slice(51, 52),
    "dynamic_range":     slice(52, 53),
    "brightness":        slice(53, 54),
    "tonal":             slice(54, 60),
}


@router.get("/{album_id}/genres/suggest")
def suggest_album_genres(
    album_id: int,
    k: int = Query(default=10, ge=1, le=100),
    m: int = Query(default=50, ge=1, le=500),
    db: Session = Depends(get_db),
):
    """Suggest genres via similarity k-NN tally."""
    album = _get_album_or_404(album_id, db)

    # Find first indexed track in album (lowest track_number with a vector)
    seed_row = db.execute(text("""
        SELECT tv.track_id, tv.feature_vector
        FROM track_vectors tv
        JOIN tracks t ON t.id = tv.track_id
        WHERE t.album_id = :album_id
        ORDER BY t.track_number ASC NULLS LAST, t.id ASC
        LIMIT 1
    """), {"album_id": album_id}).fetchone()

    if not seed_row:
        raise HTTPException(status_code=404, detail="No indexed tracks in this album")

    norm = db.get(models.VectorNormParams, 1)
    if not norm:
        raise HTTPException(status_code=404, detail="Norm params not available")

    # Fetch all vectors with album_id
    all_rows = db.execute(text("""
        SELECT tv.track_id, tv.feature_vector, t.album_id
        FROM track_vectors tv
        JOIN tracks t ON t.id = tv.track_id
    """)).fetchall()

    if len(all_rows) < 2:
        return []

    track_ids = np.array([r.track_id for r in all_rows])
    album_ids = np.array([r.album_id for r in all_rows])
    matrix = np.array([r.feature_vector for r in all_rows], dtype=np.float32)

    means = np.array(norm.means, dtype=np.float32)
    stds = np.array(norm.stds, dtype=np.float32)
    stds[stds == 0] = 1.0
    matrix = (matrix - means) / stds

    row_norms = np.linalg.norm(matrix, axis=1, keepdims=True)
    row_norms[row_norms == 0] = 1.0
    matrix /= row_norms

    # Build query vector
    seed_vec = np.array(seed_row.feature_vector, dtype=np.float32)
    seed_vec = (seed_vec - means) / stds
    seed_norm = np.linalg.norm(seed_vec)
    if seed_norm > 0:
        seed_vec /= seed_norm

    # Cosine similarities
    sims = matrix @ seed_vec

    # Sort by similarity descending
    order = np.argsort(sims)[::-1]

    # Walk neighbors, skip same album, collect until k tagged tracks or m checked
    genre_tally: dict[str, int] = {}
    tagged_count = 0
    checked = 0

    for idx in order:
        if album_ids[idx] == album_id:
            continue
        if checked >= m:
            break
        checked += 1

        tid = int(track_ids[idx])
        genre_rows = db.execute(text("""
            SELECT g.name
            FROM genres g
            JOIN track_genres tg ON tg.genre_id = g.id
            WHERE tg.track_id = :track_id
        """), {"track_id": tid}).fetchall()

        if genre_rows:
            tagged_count += 1
            for gr in genre_rows:
                name = gr.name.lower()
                genre_tally[name] = genre_tally.get(name, 0) + 1
            if tagged_count >= k:
                break

    if not genre_tally:
        return []

    existing = _existing_genre_names(album_id, db)

    # Sort by count DESC, exclude existing, top 3
    sorted_genres = sorted(genre_tally.items(), key=lambda x: x[1], reverse=True)
    suggestions = []
    for name, count in sorted_genres:
        if name in existing:
            continue
        suggestions.append({"name": name, "source": "similarity", "weight": count})
        if len(suggestions) >= 3:
            break

    return suggestions


@router.post("/{album_id}/genres", status_code=201)
def add_album_genre(
    album_id: int,
    body: dict = Body(...),
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    """Add a genre to all tracks in the album."""
    album = _get_album_or_404(album_id, db)

    name = body.get("name", "").strip().lower()
    if not name:
        raise HTTPException(status_code=422, detail="name is required")

    # Get or create genre
    genre = db.query(models.Genre).filter_by(name=name).first()
    if not genre:
        genre = models.Genre(name=name)
        db.add(genre)
        db.flush()  # populate genre.id

    # Insert track_genres for all tracks in album, ignoring duplicates
    for track in album.tracks:
        existing = db.query(models.TrackGenre).filter_by(
            track_id=track.id, genre_id=genre.id
        ).first()
        if not existing:
            db.add(models.TrackGenre(track_id=track.id, genre_id=genre.id))

    db.commit()
    return {"id": genre.id, "name": genre.name}


@router.delete("/{album_id}/genres/{genre_id}", status_code=204)
def remove_album_genre(
    album_id: int,
    genre_id: int,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    """Remove a genre from all tracks in the album."""
    _get_album_or_404(album_id, db)

    db.execute(text("""
        DELETE FROM track_genres
        WHERE genre_id = :genre_id
          AND track_id IN (SELECT id FROM tracks WHERE album_id = :album_id)
    """), {"genre_id": genre_id, "album_id": album_id})
    db.commit()
