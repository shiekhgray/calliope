#!/usr/bin/env python3
"""
bandcamp_import.py — Import Bandcamp zip files into the Calliope music library.

Bandcamp zip format:
  Artist - Album - 01 Track Title.mp3
  Artist - Album - 02 Track Title.mp3
  cover.jpg

Output structure (matching Calliope's expected layout):
  {music_root}/Artist/Album/01 Track Title.mp3
  {music_root}/Artist/Album/Folder.jpg

Usage:
  python3 scripts/bandcamp_import.py file.zip [file2.zip ...]
  python3 scripts/bandcamp_import.py *.zip
  python3 scripts/bandcamp_import.py --music-root /custom/path file.zip
"""

import argparse
import re
import shutil
import sys
import zipfile
from pathlib import Path

MUSIC_ROOT = Path("/var/www/html/calliope/music")

AUDIO_EXTENSIONS = {".mp3", ".m4a", ".wav", ".flac", ".ogg", ".opus"}


def parse_zip_name(zip_path: Path) -> tuple[str, str]:
    """
    Derive (artist, album) from zip filename: 'Artist - Album.zip'
    Falls back to ('Unknown Artist', stem) if the pattern doesn't match.
    """
    stem = zip_path.stem  # e.g. "Ninajirachi - I Love My Computer"
    if " - " in stem:
        artist, _, album = stem.partition(" - ")
        return artist.strip(), album.strip()
    return "Unknown Artist", stem.strip()


def strip_prefix(filename: str, artist: str, album: str) -> str:
    """
    Remove the 'Artist - Album - ' prefix from a track filename.
    Handles slight variations in spacing or artist name per track
    (e.g. featuring artists on individual tracks).
    Falls back to keeping the full filename if the pattern isn't found.
    """
    # Match any "anything - Album - " prefix
    pattern = rf"^.+?\s+-\s+{re.escape(album)}\s+-\s+"
    m = re.match(pattern, filename)
    if m:
        return filename[m.end():]
    # Try simpler: if filename starts with "Artist - Album - ", strip it
    prefix = f"{artist} - {album} - "
    if filename.startswith(prefix):
        return filename[len(prefix):]
    return filename


def import_zip(zip_path: Path, music_root: Path, dry_run: bool = False) -> bool:
    artist, album = parse_zip_name(zip_path)
    dest_dir = music_root / artist / album

    print(f"\n{'[DRY RUN] ' if dry_run else ''}Importing: {zip_path.name}")
    print(f"  → {dest_dir}")

    try:
        with zipfile.ZipFile(zip_path, "r") as zf:
            names = zf.namelist()

            audio_files = [n for n in names if Path(n).suffix.lower() in AUDIO_EXTENSIONS]
            has_cover = any(n.lower() == "cover.jpg" for n in names)

            if not audio_files:
                print(f"  WARNING: no audio files found in {zip_path.name}, skipping.")
                return False

            print(f"  {len(audio_files)} audio file(s){', cover.jpg found' if has_cover else ''}")

            if not dry_run:
                dest_dir.mkdir(parents=True, exist_ok=True)

            for name in audio_files:
                track_name = strip_prefix(Path(name).name, artist, album)
                dest_file = dest_dir / track_name
                if dry_run:
                    print(f"  [dry] {name!r} → {dest_file.relative_to(music_root)}")
                else:
                    data = zf.read(name)
                    dest_file.write_bytes(data)
                    print(f"  + {track_name}")

            if has_cover:
                cover_src = next(n for n in names if n.lower() == "cover.jpg")
                folder_dest = dest_dir / "Folder.jpg"
                if dry_run:
                    print(f"  [dry] cover.jpg → {folder_dest.relative_to(music_root)}")
                else:
                    data = zf.read(cover_src)
                    folder_dest.write_bytes(data)
                    print(f"  + Folder.jpg")

    except zipfile.BadZipFile:
        print(f"  ERROR: {zip_path.name} is not a valid zip file.", file=sys.stderr)
        return False

    if not dry_run:
        print(f"  Done → {artist}/{album}/")
    return True


def main():
    parser = argparse.ArgumentParser(description="Import Bandcamp zip files into Calliope music library.")
    parser.add_argument("zips", nargs="+", type=Path, help="Zip file(s) to import")
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

    if not args.dry_run and not args.music_root.exists():
        print(f"ERROR: music root does not exist: {args.music_root}", file=sys.stderr)
        sys.exit(1)

    success = 0
    for zip_path in args.zips:
        if not zip_path.exists():
            print(f"ERROR: file not found: {zip_path}", file=sys.stderr)
            continue
        if import_zip(zip_path, args.music_root, dry_run=args.dry_run):
            success += 1

    total = len(args.zips)
    print(f"\n{'[DRY RUN] ' if args.dry_run else ''}{success}/{total} zip(s) imported.")
    if not args.dry_run and success:
        print("Run 'Rescan Library' in the web UI (or: docker compose exec api python scripts/scan.py) to index the new tracks.")


if __name__ == "__main__":
    main()
