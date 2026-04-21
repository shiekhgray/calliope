# PRD: Web-Based Music Import

## Goal

Replace the terminal-based import workflow with a drag-and-drop web page. Drop one or
more zip files onto the page, watch them extract into the library, then trigger a rescan
— all without SSH or a command line.

Supports both Bandcamp and Amazon Music zip formats. Auth required (owner account only).

---

## User-Facing Behavior

### Import page

A new `/import` route, linked from the user menu (alongside "Rescan Library"). Only
visible when logged in.

The page has a large drop zone:

> **Drop zip files here**
> or click to browse

Multiple files can be dropped at once. Each file gets its own status row below the
drop zone as it processes:

```
Ninajirachi - I Love My Computer.zip    ✓ 12 tracks imported → Ninajirachi / I Love My Computer
The Smile - A Light for Attracting...   ✓ 9 tracks imported  → The Smile / A Light for Attracting Attention
bad_bunny__nadie_sabe.zip               ✗ Could not detect artist/album — rename to "Artist - Album.zip"
```

After all uploads complete, a "Rescan Library" button appears (pre-clicked automatically
if all imports succeeded). The existing scanner status polling shows progress.

### Duplicate handling

If the destination directory already exists, the import proceeds and overwrites files
with the same name. This matches the existing `bandcamp_import.py` behavior and handles
re-importing a fixed zip gracefully.

### Error states

- Not a valid zip → row shows error, skip
- No audio files found in zip → row shows warning, skip
- Could not detect Artist/Album from filename and zip contents → row shows error with
  rename hint
- Upload too large (over 600 MB per file) → rejected before upload starts (client-side check)

---

## Zip Format Detection

Two formats are supported. Detection is automatic based on zip contents and filename.

### Bandcamp format

Filename: `Artist - Album.zip`

Tracks inside the zip are flat (no subdirectory) and named:
```
Artist - Album - 01 Track Title.mp3
cover.jpg
```

Detection: filename matches `* - *.zip` AND tracks inside are flat (no subdirectory
structure) AND track filenames contain ` - `.

Extraction:
- Artist/album derived from zip filename
- `Artist - Album - ` prefix stripped from each track filename
- `cover.jpg` → `Folder.jpg`

### Amazon Music format

Filename: arbitrary (e.g. `2024-11-15.zip` or `bad_bunny__nadie_sabe.zip`)

Tracks inside the zip are in a subdirectory structure:
```
Artist Name/
  Album Title/
    01 - Track.mp3
    02 - Track.mp3
```

Amazon encodes `/` as `__` in filenames (visible in zip entry names and sometimes
the zip filename itself). The subdirectory structure is the authoritative source of
artist and album name — ID3 tags are not consulted during import.

Detection: zip contains a two-level directory structure (artist dir → album dir →
audio files).

Extraction:
- Artist and album derived from the subdirectory names
- `__` → `/` applied to directory and file names when creating destination paths
- No cover art handling (Amazon zips don't include it; album art can be uploaded
  separately via the album page)

### Fallback

If neither format is detected, the import fails with a "Could not detect format" error
and a hint to rename the file to `Artist - Album.zip`.

---

## API

### `POST /import/upload`

Auth required. Accepts `multipart/form-data` with one or more files under the `files`
field. Processes each file sequentially (not in parallel — disk I/O bound, not CPU
bound). Returns immediately with per-file results; does **not** trigger a rescan.

Request: `multipart/form-data`, field name `files`, multiple files allowed.

Response:
```json
{
  "results": [
    {
      "filename": "Ninajirachi - I Love My Computer.zip",
      "status": "ok",
      "artist": "Ninajirachi",
      "album": "I Love My Computer",
      "tracks_imported": 12
    },
    {
      "filename": "bad_bunny.zip",
      "status": "error",
      "message": "Could not detect artist/album. Rename to 'Artist - Album.zip' or use a zip with Artist/Album subdirectory structure."
    }
  ]
}
```

Status values: `"ok"` | `"error"` | `"warning"` (no audio files).

The endpoint is synchronous — it blocks until all files are extracted. For typical
album zips (10–100 MB each) this completes in under a second on local SSD. No
background task needed.

### Nginx

`client_max_body_size` must be set on the `/calliope/api/` location block. 600 MB
covers the largest realistic multi-album upload. Add to `nginx/calliope.conf`:

```nginx
client_max_body_size 600M;
```

Also add to the API location block:
```nginx
proxy_read_timeout 120s;
```

---

## Implementation Plan

### Backend

1. `api/app/routers/import_music.py` — `POST /import/upload`; format detection;
   Bandcamp and Amazon extraction logic ported from `scripts/bandcamp_import.py`;
   returns per-file result list
2. `api/app/main.py` — register the new router at prefix `/import`
3. `nginx/calliope.conf` — add `client_max_body_size 600M` and `proxy_read_timeout 120s`
   to the `/calliope/api/` location block

No new migration needed — import writes files to disk, rescan handles DB.

### Frontend

4. `web/src/pages/ImportPage.jsx` — drop zone (click or drag), per-file status rows,
   auto-trigger rescan on full success, scanner status polling (reuse existing pattern)
5. `web/src/components/Layout.jsx` — add "Import Music" link to user menu (auth-gated,
   same as "Rescan Library")
6. `web/src/App.jsx` (or router file) — register `/import` route

### CSS

Reuse existing dark theme patterns. New classes:
- `.import-dropzone` — large dashed border box, accent color on drag-over
- `.import-file-list` — result rows below the drop zone
- `.import-file-row` — filename + status + detail (flex row)
- `.import-status-ok`, `.import-status-error`, `.import-status-warning` — colored dot/icon

---

## Out of Scope

- Loose directory uploads (zip only)
- Format conversion / transcoding
- Duplicate detection beyond "directory already exists"
- Progress streaming for individual file extraction (synchronous response is fine)
- Multi-user upload permissions (owner-only is sufficient)
- The existing `scripts/bandcamp_import.py` is **not** removed — it remains useful
  for bulk imports and scripted workflows
