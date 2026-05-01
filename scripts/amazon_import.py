#!/usr/bin/env python3
"""
amazon_import.py — Import Amazon Music zip files or loose singles into the Calliope music library.

Amazon zip format:
  Artist/Album/01 - Track Title.mp3
  Artist/Album/02 - Track Title.mp3
  (no cover art included)

Amazon single format (loose .mp3/.m4a):
  01 - Track Title.mp3   (ID3 tags carry artist/album metadata)

Output structure (matching Calliope's expected layout):
  {music_root}/Artist/Album/01 - Track Title.mp3

Usage:
  python3 scripts/amazon_import.py file.zip [file2.zip ...]
  python3 scripts/amazon_import.py --loose track.mp3 [cover.jpg]
  python3 scripts/amazon_import.py --music-root /custom/path file.zip
  python3 scripts/amazon_import.py --dry-run file.zip
"""

import argparse
import re
import sys
import zipfile
from pathlib import Path
from typing import Optional

MUSIC_ROOT = Path("/var/www/html/calliope/music")

AUDIO_EXTENSIONS = {".mp3", ".m4a", ".wav", ".flac", ".ogg", ".opus"}


def primary_artist(albumartist: str) -> str:
    """Extract primary artist from a collaboration tag like 'GUNSHIP, Lights feat. Tim Cappello'."""
    # Split on ', ' or ' feat.' (case-insensitive), take the first segment
    part = re.split(r",\s*|\sfeat\.\s*", albumartist, maxsplit=1, flags=re.IGNORECASE)[0]
    return part.strip()


def import_loose(audio_path: Path, music_root: Path, cover_path: Optional[Path] = None, dry_run: bool = False) -> bool:
    print(f"\n{'[DRY RUN] ' if dry_run else ''}Importing loose single: {audio_path.name}")

    try:
        from mutagen import File as MutagenFile
    except ImportError:
        print("  ERROR: mutagen is required for loose single import. Install with: pip install mutagen", file=sys.stderr)
        return False

    tags = MutagenFile(audio_path, easy=True)
    if tags is None:
        print(f"  ERROR: could not read tags from {audio_path.name}", file=sys.stderr)
        return False

    raw_albumartist = (tags.get("albumartist") or tags.get("artist") or [None])[0]
    album = (tags.get("album") or [None])[0]
    title = (tags.get("title") or [None])[0]

    if not raw_albumartist or not album:
        print(f"  ERROR: missing albumartist or album tag in {audio_path.name}", file=sys.stderr)
        print(f"    albumartist={raw_albumartist!r}  album={album!r}", file=sys.stderr)
        return False

    artist = primary_artist(raw_albumartist)

    dest_dir = music_root / artist / album
    dest_file = dest_dir / audio_path.name

    print(f"  albumartist tag : {raw_albumartist!r}")
    print(f"  → artist dir    : {artist!r}")
    print(f"  → album dir     : {album!r}")
    print(f"  → title         : {title!r}")
    print(f"  → destination   : {dest_file}")

    if cover_path:
        dest_cover = dest_dir / "Folder.jpg"
        print(f"  → cover art     : {cover_path.name} → {dest_cover}")

    if not dry_run:
        dest_dir.mkdir(parents=True, exist_ok=True)
        dest_file.write_bytes(audio_path.read_bytes())
        print(f"  + {audio_path.name}")
        if cover_path:
            dest_cover = dest_dir / "Folder.jpg"
            dest_cover.write_bytes(cover_path.read_bytes())
            print(f"  + Folder.jpg")

    return True


def import_zip(zip_path: Path, music_root: Path, dry_run: bool = False) -> bool:
    print(f"\n{'[DRY RUN] ' if dry_run else ''}Importing: {zip_path.name}")

    try:
        with zipfile.ZipFile(zip_path, "r") as zf:
            names = zf.namelist()

            # Find audio files that are at least 2 levels deep (Artist/Album/Track)
            audio_entries = []
            for name in names:
                p = Path(name)
                if p.suffix.lower() in AUDIO_EXTENSIONS and len(p.parts) >= 3:
                    audio_entries.append(name)

            if not audio_entries:
                print(f"  WARNING: no audio files found at Artist/Album/Track depth, skipping.")
                return False

            # Group by album for summary
            albums = set()
            for name in audio_entries:
                parts = Path(name).parts
                albums.add(f"{parts[0]}/{parts[1]}")

            for album in sorted(albums):
                dest = music_root / album
                count = sum(1 for n in audio_entries if Path(n).parts[:2] == tuple(album.split("/", 1)))
                print(f"  {album}/ — {count} track(s) → {dest}")

            if not dry_run:
                for name in audio_entries:
                    parts = Path(name).parts
                    dest_file = music_root / Path(*parts)
                    dest_file.parent.mkdir(parents=True, exist_ok=True)
                    data = zf.read(name)
                    dest_file.write_bytes(data)
                    print(f"  + {Path(name).name}")
            else:
                for name in audio_entries:
                    dest_file = music_root / Path(name)
                    print(f"  [dry] {name!r} → {dest_file}")

    except zipfile.BadZipFile:
        print(f"  ERROR: {zip_path.name} is not a valid zip file.", file=sys.stderr)
        return False

    if not dry_run:
        print(f"  Done.")
    return True


def main():
    parser = argparse.ArgumentParser(description="Import Amazon Music zip files or loose singles into Calliope music library.")
    parser.add_argument("files", nargs="*", type=Path, help="Zip file(s) to import (or audio file + optional cover.jpg with --loose)")
    parser.add_argument(
        "--loose",
        action="store_true",
        help="Import a loose single MP3/M4A using its ID3 tags to determine Artist/Album placement",
    )
    parser.add_argument(
        "--music-root",
        type=Path,
        default=MUSIC_ROOT,
        help=f"Music library root (default: {MUSIC_ROOT})",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Show what would be imported without writing any files",
    )
    args = parser.parse_args()

    if not args.files:
        parser.print_help()
        sys.exit(1)

    if not args.dry_run and not args.music_root.exists():
        print(f"ERROR: music root does not exist: {args.music_root}", file=sys.stderr)
        sys.exit(1)

    if args.loose:
        audio_path = args.files[0]
        cover_path = args.files[1] if len(args.files) > 1 else None
        if not audio_path.exists():
            print(f"ERROR: file not found: {audio_path}", file=sys.stderr)
            sys.exit(1)
        if cover_path and not cover_path.exists():
            print(f"ERROR: cover file not found: {cover_path}", file=sys.stderr)
            sys.exit(1)
        success = import_loose(audio_path, args.music_root, cover_path=cover_path, dry_run=args.dry_run)
    else:
        success_count = 0
        for zip_path in args.files:
            if not zip_path.exists():
                print(f"ERROR: file not found: {zip_path}", file=sys.stderr)
                continue
            if import_zip(zip_path, args.music_root, dry_run=args.dry_run):
                success_count += 1
        total = len(args.files)
        print(f"\n{'[DRY RUN] ' if args.dry_run else ''}{success_count}/{total} zip(s) imported.")
        success = success_count > 0

    if not args.dry_run and success:
        print("Run 'Rescan Library' in the web UI (or: docker compose exec api python scripts/scan.py) to index the new tracks.")


if __name__ == "__main__":
    main()
