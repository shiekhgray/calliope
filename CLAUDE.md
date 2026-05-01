# Calliope 2

A personal music streaming service. Two users (owner + wife), playlist management, genre tagging, album art, native Android app with Android Auto support.

## Architecture Overview

```
calliope/
  api/              ← FastAPI (Python), Docker; code baked into image (rebuild required on changes)
  indexer/          ← Similarity engine; separate Docker container
  web/              ← React + Vite; src volume-mounted for HMR (edit on host, instant reload)
  android/          ← Kotlin + Jetpack Compose (not yet started)
  nginx/            ← config snippets; deployed at /etc/nginx/default.d/calliope.conf
  scripts/          ← host-side utilities
  prd/              ← one PRD per feature/phase
  .claude/commands/ ← expert agent slash commands
  .todo             ← lean PRD index (done / up next / later)
```

## Tech Stack

| Layer | Technology |
|---|---|
| API | Python, FastAPI, uvicorn |
| Indexer | Python stdlib HTTP server, librosa, numpy, pgvector |
| Database | PostgreSQL 16 (`pgvector/pgvector:pg16` image — stock `postgres:16` lacks vector extension) |
| Migrations | Alembic |
| ORM | SQLAlchemy |
| Auth | JWT (python-jose + bcrypt) — passlib dropped, incompatible with bcrypt 4.x |
| Audio tags | Mutagen |
| Web | React, Vite, React Router, React Query, node-vibrant v4 |
| Android | Kotlin, Jetpack Compose, Media3/ExoPlayer |
| Proxy | Nginx (proxies `/calliope/api/` → 8000, `/calliope` → 5173) |

## Infrastructure

- **Music files**: `/backup/calliope/music/` — mounted **read-write** (album art upload writes `Folder.jpg`)
- **Public URL**: `https://dresdengray.com/calliope/` — HTTPS via Let's Encrypt, auto-renewing
- **Migrations**: run manually — `docker compose exec api alembic upgrade head` — applied 0001–0007
- **API changes**: require `docker compose build api && docker compose up -d api` (code baked into image)
- **nginx config**: `/etc/nginx/default.d/calliope.conf`. Apply: `sudo nginx -s reload`
- **Docker**: use `docker compose` (v2 plugin). `version:` header in compose file is obsolete — harmless.
- **Docker storage driver**: `/etc/docker/daemon.json` sets `overlay2` — do not remove (devicemapper legacy)
- **Node.js on host**: system install is v14; use `nvm use 22`. Docker uses `node:22-slim` (unaffected).

## Users

- id=1 — owner
- id=2 `thefacesblur` — change password after seeding
- id=3 `clippy` / `Tr0mb0ne!` — **use this for dev/smoke testing**

## Music Library

- Location: `/backup/calliope/music/`, structure: `Artist/Album/Track.mp3`
- Formats: MP3, M4A, WAV. Duplicate `.mp3`/`.m4a` tracks exist — do not deduplicate.
- Album art: `Folder.jpg` → `AlbumArt*_Large.jpg` → first `.jpg` (stored as files, not embedded in ID3)
- Noise files (`desktop.ini`, `.DS_Store`, `.db`) present — scanner ignores them
- **Do not use real artist/album names for test data** — writes to the live music library
- **Moving a directory orphans tracks**: scanner matches by `file_path`. After any `mv`:
  ```sql
  DELETE FROM track_genres WHERE track_id IN (SELECT id FROM tracks WHERE file_path LIKE 'OldPath/%');
  DELETE FROM track_vectors WHERE track_id IN (SELECT id FROM tracks WHERE file_path LIKE 'OldPath/%');
  DELETE FROM tracks WHERE file_path LIKE 'OldPath/%';
  ```
- **Moving a directory breaks album art**: `cover_art_path` is baked into the `albums` row. Fix:
  ```sql
  UPDATE albums SET cover_art_path = 'NewPath/Folder.jpg' WHERE id = ...;
  ```
- **albumartist tag mismatches** create duplicate artists. Fix by retagging + rescan + manual DB merge.

## Database Schema

```
users              id, username, password_hash
artists            id, name
albums             id, artist_id, title, year, cover_art_path
tracks             id, album_id, title, track_number, duration_ms, bitrate_kbps, file_path, format,
                   play_count, track_artist (varchar nullable), track_artist_id (FK→artists nullable)
genres             id, name
track_genres       track_id, genre_id
playlists          id, owner_id, title, description, created_at
playlist_tracks    id, playlist_id, track_id, position
discoveries        id, artist_id, itunes_collection_id (unique bigint), album_title, release_date,
                   artwork_url, dismissed, first_seen_at
search_history     id, user_id, entity_type ('artist'|'album'|'track'), entity_id, visited_at;
                   UNIQUE(user_id, entity_type, entity_id)
track_vectors      track_id (FK unique), feature_vector vector(38), file_mtime bigint
vector_norm_params id (always 1), means float[38], stds float[38], updated_at
```

- `cover_art_path` is relative from music root; served via API (no direct filesystem exposure)
- `play_count` — scanner never touches it; rescan is always safe
- `track_artist` / `track_artist_id` — set on compilation tracks; NULL on normal tracks. **Planned retirement**: migration 0008 (`track-credits` PRD) will replace both with `track_credits (track_id, artist_id)` + `album_artists (album_id, artist_id)`.
- `GET /artists` excludes "Various Artists" (kept in DB, filtered at query time)

## Non-Obvious Rules

### API
- **Explicit dicts**: several endpoints return dicts (not raw ORM models) to include joined fields (`artist_name`, `album_title`). Do not convert back to model returns — joined fields will silently disappear.
- **Login is OAuth2 form-encoded**: `POST /auth/login` takes `application/x-www-form-urlencoded`, NOT JSON. Curl: `-d 'username=X&password=Y'`.
- **Byte-range streaming required** on `/tracks/{id}/stream` — enables seeking in HTML5 Audio + ExoPlayer.
- **Scanner is two-phase**: trigger → `scan.py` subprocess → then calls indexer container to re-index.

### Web
- **Hardcoded API URLs** (img src, audio.src, etc.) must use `/calliope/api/` prefix. The axios client has `baseURL: '/calliope/api'` already; anything bypassing it needs the full prefix.
- **Track enrichment**: always pass `album_id`, `album_title`, `artist_id`, `artist_name` to `playTrack()`. Missing fields silently drop PlayerBar links.
- **isPlaying**: `null` = nothing ever loaded; `false` = loaded but paused; `true` = playing.
- **Dynamic accent**: CSS `@property` + transition was tried and scrapped — Chromium interpolates `@property <color>` in OKLab, causing washed-out flashes on hue shifts. JS sRGB via `requestAnimationFrame` is used instead.

## Expert Agents (`.claude/commands/`)

Use these when working in a subsystem — each loads its own file context:

- `/api` — FastAPI backend, routers, models, migrations, scanner
- `/web` — React frontend, player, auth, CSS
- `/similarity` — MFCC/chroma pipeline, pgvector, radio mode
- `/android` — Kotlin/Compose/ExoPlayer (not yet coded)
- `/import-music` — import zips from `~/Music/` staging area
- `/coffee` / `/beer` — session start / save state

## Planned Features

See `.todo` for status. Full specs in `prd/`.

Up next: Genre Tagging, Playlist Permissions, Playlist Cards, Vector Expansion, Similarity Weights, Phase 5 Android.

## Development Constraints

- No iOS support (no Apple devices in use)
- No transcoding — serve files as-is
- No browser offline support
- No metadata enrichment (MusicBrainz etc.) — deferred to a future project
