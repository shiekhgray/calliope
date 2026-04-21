#!/usr/bin/env python3
"""
amazon_import.py — Import Amazon Music zip files into the Calliope music library.

Amazon zip format:
  Artist/Album/01 - Track Title.mp3
  Artist/Album/02 - Track Title.mp3
  (no cover art included)

Output structure (matching Calliope's expected layout):
  {music_root}/Artist/Album/01 - Track Title.mp3

Usage:
  python3 scripts/amazon_import.py file.zip [file2.zip ...]
  python3 scripts/amazon_import.py --music-root /custom/path file.zip
  python3 scripts/amazon_import.py --dry-run file.zip
"""

import argparse
import sys
import zipfile
from pathlib import Path

MUSIC_ROOT = Path("/var/www/html/calliope/music")

AUDIO_EXTENSIONS = {".mp3", ".m4a", ".wav", ".flac", ".ogg", ".opus"}


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
    parser = argparse.ArgumentParser(description="Import Amazon Music zip files into Calliope music library.")
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
