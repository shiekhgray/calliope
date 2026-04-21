# Bandcamp Import Script

**Status: Complete**

## What Was Built

`scripts/bandcamp_import.py` — imports Bandcamp zip files into the Calliope music library.

## Usage

```bash
python3 scripts/bandcamp_import.py file.zip [file2.zip ...]
python3 scripts/bandcamp_import.py --dry-run *.zip
python3 scripts/bandcamp_import.py --music-root /custom/path file.zip
```

After import, trigger a rescan via the web UI (Releases → Rescan Library) or:
```bash
docker compose exec api python scripts/scan.py
```

## How It Works

Bandcamp zips follow the naming convention: `Artist - Album.zip`, with tracks named `Artist - Album - 01 Track Title.mp3` and a `cover.jpg` at the root.

The script:
1. Derives artist + album from the zip filename (`Artist - Album.zip`)
2. Strips the `Artist - Album - ` prefix from each track filename
3. Writes audio files to `{music_root}/Artist/Album/`
4. Renames `cover.jpg` → `Folder.jpg` (matching Calliope's art priority order)

## Key Decisions

- Track 11 of "I Love My Computer" has a featuring artist in the filename (`Ninajirachi & daine - ...`). The album-title-based prefix strip handles this correctly — it matches on album name rather than requiring an exact artist name match.
- `--dry-run` flag for safe previewing before writing
- Default music root: `/var/www/html/calliope/music`
- Supported formats: `.mp3`, `.m4a`, `.wav`, `.flac`, `.ogg`, `.opus`
