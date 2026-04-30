#!/usr/bin/env python3
"""
qobuz_import.py — Import Qobuz zip files into the Calliope music library.

Qobuz zip format:
  Artist - Album/01 Track Title.flac
  Artist - Album/02 Track Title.flac
  (no cover art included)

Output structure:
  {music_root}/Artist/Album/01 Track Title.mp3

FLACs are transcoded to MP3 V0 (VBR ~245kbps) via ffmpeg. ffmpeg must be
installed (Fedora: sudo dnf install ffmpeg, requires RPM Fusion).

Usage:
  python3 scripts/qobuz_import.py file.zip [file2.zip ...]
  python3 scripts/qobuz_import.py --music-root /custom/path file.zip
  python3 scripts/qobuz_import.py --dry-run file.zip
"""

import argparse
import shutil
import subprocess
import sys
import tempfile
import zipfile
from pathlib import Path

MUSIC_ROOT = Path("/backup/calliope/music")

AUDIO_EXTENSIONS = {".flac", ".mp3", ".m4a", ".wav"}


def check_ffmpeg():
    if not shutil.which("ffmpeg"):
        print(
            "ERROR: ffmpeg not found. Install it first:\n"
            "  sudo dnf install https://mirrors.rpmfusion.org/free/fedora/"
            "rpmfusion-free-release-$(rpm -E %fedora).noarch.rpm\n"
            "  sudo dnf install ffmpeg",
            file=sys.stderr,
        )
        sys.exit(1)


def parse_subdir(subdir: str) -> tuple[str, str]:
    """
    Derive (artist, album) from 'Artist - Album' subdirectory name.
    Falls back to ('Unknown Artist', subdir) if pattern doesn't match.
    """
    if " - " in subdir:
        artist, _, album = subdir.partition(" - ")
        return artist.strip(), album.strip()
    return "Unknown Artist", subdir.strip()


def transcode_to_mp3(src: Path, dest: Path):
    """Convert src (FLAC) to dest (MP3 V0) via ffmpeg."""
    subprocess.run(
        ["ffmpeg", "-y", "-loglevel", "error", "-i", str(src), "-q:a", "0", str(dest)],
        check=True,
    )


def import_zip(zip_path: Path, music_root: Path, dry_run: bool = False) -> bool:
    print(f"\n{'[DRY RUN] ' if dry_run else ''}Importing: {zip_path.name}")

    try:
        with zipfile.ZipFile(zip_path, "r") as zf:
            names = zf.namelist()

            # Expect entries like "Artist - Album/01 Title.flac"
            audio_entries = [
                n for n in names
                if len(Path(n).parts) == 2 and Path(n).suffix.lower() in AUDIO_EXTENSIONS
            ]

            if not audio_entries:
                print(f"  WARNING: no audio files found in expected 'Artist - Album/Track' layout, skipping.")
                return False

            # All tracks should share one subdirectory
            subdirs = {Path(n).parts[0] for n in audio_entries}
            if len(subdirs) > 1:
                print(f"  WARNING: multiple subdirectories found: {subdirs}. Importing all.")

            for subdir in sorted(subdirs):
                artist, album = parse_subdir(subdir)
                dest_dir = music_root / artist / album
                tracks = [n for n in audio_entries if Path(n).parts[0] == subdir]
                print(f"  {artist} / {album} — {len(tracks)} track(s) → {dest_dir}")

                if dry_run:
                    for name in sorted(tracks):
                        src_name = Path(name).name
                        dest_name = Path(src_name).with_suffix(".mp3").name
                        print(f"  [dry] {src_name!r} → {dest_dir / dest_name}")
                    continue

                dest_dir.mkdir(parents=True, exist_ok=True)

                with tempfile.TemporaryDirectory() as tmp:
                    tmp_path = Path(tmp)
                    for name in sorted(tracks):
                        src_name = Path(name).name
                        dest_name = Path(src_name).with_suffix(".mp3").name
                        dest_file = dest_dir / dest_name

                        # Extract FLAC to temp dir, transcode, write to library
                        tmp_flac = tmp_path / src_name
                        tmp_flac.write_bytes(zf.read(name))
                        transcode_to_mp3(tmp_flac, dest_file)
                        print(f"  + {dest_name}")

    except zipfile.BadZipFile:
        print(f"  ERROR: {zip_path.name} is not a valid zip file.", file=sys.stderr)
        return False
    except subprocess.CalledProcessError as e:
        print(f"  ERROR: ffmpeg failed: {e}", file=sys.stderr)
        return False

    if not dry_run:
        print(f"  Done → {artist}/{album}/")
    return True


def main():
    parser = argparse.ArgumentParser(description="Import Qobuz zip files into Calliope music library.")
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

    if not args.dry_run:
        check_ffmpeg()
        if not args.music_root.exists():
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
