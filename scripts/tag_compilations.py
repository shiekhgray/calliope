#!/usr/bin/env python3
"""
Tag all tracks under Various Artists/ with albumartist = "Various Artists".
Run with --dry-run to preview without writing.
"""

import argparse
import sys
from pathlib import Path

try:
    from mutagen.easyid3 import EasyID3
    from mutagen.easymp4 import EasyMP4
    from mutagen.id3 import ID3NoHeaderError
except ImportError:
    print("mutagen not found. Install with: pip3 install mutagen")
    sys.exit(1)

MUSIC_ROOT = Path("/backup/calliope/music/Various Artists")
AUDIO_EXTS = {".mp3", ".m4a", ".wav"}


def tag_file(path: Path, dry_run: bool):
    """Returns 'set', 'already_set', or None on skip/error."""
    ext = path.suffix.lower()
    try:
        if ext == ".mp3":
            try:
                tags = EasyID3(path)
            except ID3NoHeaderError:
                tags = EasyID3()
                tags.save(path)
                tags = EasyID3(path)
            current = tags.get("albumartist", [])
            if current == ["Various Artists"]:
                return "already_set"
            if not dry_run:
                tags["albumartist"] = ["Various Artists"]
                tags.save()
            return "set"

        elif ext == ".m4a":
            tags = EasyMP4(path)
            current = tags.get("aART", [])
            if current == ["Various Artists"]:
                return "already_set"
            if not dry_run:
                tags["aART"] = ["Various Artists"]
                tags.save()
            return "set"

    except Exception as e:
        print(f"  ERROR {path}: {e}")
        return None

    return None  # unsupported format (e.g. .wav — no standard albumartist tag)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dry-run", action="store_true", help="Preview without writing")
    parser.add_argument("--music-root", default=str(MUSIC_ROOT), help="Path to Various Artists dir")
    args = parser.parse_args()

    root = Path(args.music_root)
    if not root.exists():
        print(f"Directory not found: {root}")
        sys.exit(1)

    dry = args.dry_run
    if dry:
        print("DRY RUN — no files will be modified\n")

    counts = {"set": 0, "already_set": 0, "skipped": 0, "error": 0}

    for audio_file in sorted(root.rglob("*")):
        if audio_file.suffix.lower() not in AUDIO_EXTS:
            continue
        result = tag_file(audio_file, dry)
        if result == "set":
            counts["set"] += 1
            verb = "Would set" if dry else "Set"
            print(f"  {verb}: {audio_file.relative_to(root.parent)}")
        elif result == "already_set":
            counts["already_set"] += 1
        elif result is None:
            counts["skipped"] += 1

    print()
    print(f"Results:")
    print(f"  {'Would tag' if dry else 'Tagged'}:    {counts['set']}")
    print(f"  Already set: {counts['already_set']}")
    print(f"  Skipped:     {counts['skipped']} (unsupported format or error)")


if __name__ == "__main__":
    main()
