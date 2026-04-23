---
allowed-tools: Bash, Read, Glob, Write, Edit
description: Scan ~/Music/ for new albums (zips or directories), extract/copy them into the Calliope music library, and trigger a rescan.
---

## Context

- Music library root: `/var/www/html/calliope/music/`
- Staging area: `/home/gray/Music/`
- Calliope project: `/home/gray/calliope/`

Scan results from staging area:
- Zip files: !`find /home/gray/Music -maxdepth 2 -name "*.zip" 2>/dev/null`
- Loose directories (non-zip folders with audio): !`find /home/gray/Music -mindepth 2 -maxdepth 2 -type d 2>/dev/null`
- Current library artists: !`ls /var/www/html/calliope/music/ | sort`

## Your task

1. **Inventory** what's in `/home/gray/Music/` — list zip files and any loose Artist/Album directories. For each zip, show its contents with `unzip -l`. For loose directories, show the file tree.

2. **Check for duplicates** — compare what you found against the existing library. Flag anything that already exists (same artist/album path).

3. **Present a summary** to the user: what will be imported, what already exists. Ask for confirmation before doing anything destructive or moving any files.

4. **On confirmation**, for each item:
   - Zip files: extract with `unzip -d /var/www/html/calliope/music <zipfile>`
   - Loose directories: copy with `cp -r` to the correct Artist/ subdirectory under the library root
   - After all items are imported, run the scanner: `cd /home/gray/calliope && docker compose exec api python scripts/scan.py`

5. **Report** the before/after track counts from the scanner output, and note any filenames with `__` (Amazon's substitute for `/` in track titles) that the user may want to verify have correct ID3 tags.

6. After a successful import, **offer to clean up** the source zips/directories from `/home/gray/Music/` (ask first, don't delete automatically).
