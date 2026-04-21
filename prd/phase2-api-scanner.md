# Phase 2: API & Library Scanner

**Status: Complete**

## What Was Built

- FastAPI skeleton with SQLAlchemy + Alembic
- All 7 DB models: `users`, `artists`, `albums`, `tracks`, `genres`, `track_genres`, `playlists`, `playlist_tracks`
- Migrations: `0001_initial`, `0002_add_track_bitrate`, `0003_add_play_count`
- Library scanner: `api/scripts/scan.py`
- All read endpoints: artists, albums, tracks, genres, search
- Byte-range streaming on `GET /tracks/{id}/stream` (512KB chunks)
- Album art: `GET /albums/{id}/art` (serve), `PUT /albums/{id}/art` (upload → writes `Folder.jpg`)
- Play count: `POST /tracks/{id}/played` (increments, auth required)
- Top tracks: `GET /artists/{id}/top-tracks` (top 10 by play_count DESC, ties by RANDOM())
- Scanner API: `POST /scanner/trigger` (auth, background task), `GET /scanner/status`

## Scanner Behavior

- Walks `Artist/Album/Track` structure; falls back to directory names if tags missing
- Mutagen for MP3/M4A/WAV tag reading
- Cover art priority: `Folder.jpg` → `AlbumArt*_Large.jpg` → first `.jpg` in dir
- Fully idempotent — safe to re-run; never touches `play_count`
- Ignores non-audio noise files (`desktop.ini`, `.DS_Store`, `.db`)
- Result: 246 artists, 392 albums, 2485 tracks (after Ninajirachi import)

## Key Decisions

- `cover_art_path` is a relative path from music root — art served through API, not exposed directly.
- Several endpoints return explicit dicts (not raw ORM models) to include joined fields like `artist_name`, `album_title`. Do not revert to raw model returns.
- `play_count` is `INTEGER NOT NULL DEFAULT 0` — scanner never touches it.
- Bitrate read from `audio.info.bitrate` (bps), stored as integer kbps. WAV may yield null — acceptable.

## Gotchas

- `scan.py` must live at `api/scripts/scan.py` (inside Docker build context).
- Scanner router path bug fixed: was resolving to `/scripts/scan.py` (one `.parent` too many); corrected to `/app/scripts/scan.py`.
- `upsert_genres` had a dead first line reading from `track.playlist_entries` (wrong relationship); removed.
- passlib 1.7.4 incompatible with bcrypt 4.x — dropped passlib, use bcrypt directly.
