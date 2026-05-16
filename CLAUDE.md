# Calliope 2

A personal music streaming service. Two users (owner + wife), playlist management, genre tagging, album art, native Android app with Android Auto support.

## Architecture Overview

```
calliope/
  api/              ← FastAPI (Python), Docker; code baked into image (rebuild required on changes)
  indexer/          ← Similarity engine; separate Docker container
  web/              ← React + Vite; src volume-mounted for HMR (edit on host, instant reload)
  android/          ← Kotlin + Jetpack Compose; Phase 5 nearly complete (auth, library, player, search, playlists, downloads, WiFi guard, similar tracks, radio mode done — APK signing remaining)
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
- **Migrations**: run manually — `docker compose exec api alembic upgrade head` — applied 0001–0012
- **API changes**: require `docker compose build api && docker compose up -d api` (code baked into image)
- **nginx config**: `/etc/nginx/default.d/calliope.conf`. Apply: `sudo nginx -s reload`
- **Docker**: use `docker compose` (v2 plugin). `version:` header in compose file is obsolete — harmless.
- **Docker storage driver**: `/etc/docker/daemon.json` sets `overlay2` — do not remove (devicemapper legacy)
- **Node.js on host**: system install is v14; use `nvm use 22`. Docker uses `node:22-slim` (unaffected).
- **Android builds (Windows)**: `JAVA_HOME` must point to Android Studio's bundled JRE — `/c/Program Files/Android/Android Studio/jbr`. Run: `JAVA_HOME="..." ./gradlew assembleDebug`. SDK at `C:\Users\shiek\AppData\Local\Android\Sdk`. `android/local.properties` must exist with `sdk.dir=C\:\\Users\\shiek\\AppData\\Local\\Android\\Sdk`.

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
users              id, username, password_hash, sim_weight_timbre, sim_weight_timbral_variation,
                   sim_weight_harmony, sim_weight_chord_movement, sim_weight_tempo,
                   sim_weight_loudness, sim_weight_dynamic_range, sim_weight_brightness,
                   sim_weight_tonal  (9 × INTEGER NOT NULL DEFAULT 5, migration 0011)
artists            id, name
albums             id, artist_id, title, year, cover_art_path,
                   album_type VARCHAR(8) NOT NULL DEFAULT 'album'  (migration 0009; values: album/ep/single)
tracks             id, album_id, title, track_number, duration_ms, bitrate_kbps, file_path, format,
                   play_count
genres             id, name
track_genres       track_id, genre_id
album_artists      album_id (FK→albums), artist_id (FK→artists) — composite PK; primary album credits
track_credits      track_id (FK→tracks), artist_id (FK→artists) — composite PK; featured/guest credits
playlists          id, owner_id, title, description, created_at,
                   view_mode VARCHAR(10) DEFAULT 'everyone',  edit_mode VARCHAR(10) DEFAULT 'owner'
                   (migration 0012)
playlist_viewers   playlist_id (FK), user_id (FK) — cascade delete (migration 0012)
playlist_editors   playlist_id (FK), user_id (FK) — cascade delete (migration 0012)
playlist_tracks    id, playlist_id, track_id, position
discoveries        id, artist_id, itunes_collection_id (unique bigint), album_title, release_date,
                   artwork_url, dismissed, first_seen_at
search_history     id, user_id, entity_type ('artist'|'album'|'track'), entity_id, visited_at;
                   UNIQUE(user_id, entity_type, entity_id)
track_vectors      track_id (FK unique), feature_vector vector(60), file_mtime bigint
                   (expanded 38→60 dims in migration 0010; HNSW index on feature_vector)
vector_norm_params id (always 1), means float[60], stds float[60], updated_at
```

- `cover_art_path` is relative from music root; served via API (no direct filesystem exposure)
- `play_count` — scanner never touches it; rescan is always safe
- `album.artist_id` — kept as the display label for album cards (scanner writes from albumartist tag). Attribution for artist pages is driven by `album_artists`; `album.artist_id` is display-only.
- `album_artists` / `track_credits` — added by migration 0008. `track_artist` and `track_artist_id` columns were dropped.
- `GET /artists` — shows artists with at least one `album_artists` row OR at least one album with no `album_artists` rows at all. Combined-credit ghost entries ("i_o & Lights") disappear automatically once their albums are claimed via `album_artists`.
- `album_type` — enforced at API layer (not DB constraint). Cycle pill on AlbumPage (owner only): album → ep → single.
- Playlist permissions: `view_mode` ('everyone'|'users') + `edit_mode` ('owner'|'users'|'everyone'); membership via `playlist_viewers`/`playlist_editors` join tables. All playlist endpoints now require auth.

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

Four expert skills cover the main subsystems. **Always run them as isolated
`general-purpose` agents** rather than inline skills — this keeps the main
context clean and allows parallel execution.

**Invocation pattern:**

```python
# Single subsystem
Agent(
    subagent_type="general-purpose",
    prompt=open(".claude/commands/api.md").read() + "\n\nTASK: " + task,
)

# Parallel (API + web simultaneously)
Agent(subagent_type="general-purpose", prompt=api_md + task_a, run_in_background=True)
Agent(subagent_type="general-purpose", prompt=web_md + task_b, run_in_background=True)
```

In practice: read the skill file with the `Read` tool, append the task
description, and pass to `Agent(subagent_type="general-purpose")`.

| Skill file | Subsystem |
|---|---|
| `.claude/commands/api.md` | FastAPI backend, routers, models, migrations, scanner |
| `.claude/commands/web.md` | React frontend, player, auth, CSS |
| `.claude/commands/similarity.md` | MFCC/chroma pipeline, pgvector, radio mode |
| `.claude/commands/android.md` | Kotlin/Compose/ExoPlayer/Android Auto |

Utility skills (still invoked inline via `Skill()`):
- `/import-music` — import zips from `~/Music/` staging area
- `/coffee` / `/beer` — session start / save state

## Planned Features

See `.todo` for status. Full specs in `prd/`.

Phase 5 Android is nearly complete. Remaining: APK signing + sideload test, Moshi kapt→ksp (non-blocking), Android Auto full implementation. All web features through migration 0012 are shipped.


## Development Constraints

- No iOS support (no Apple devices in use)
- No transcoding — serve files as-is
- No browser offline support
- No metadata enrichment (MusicBrainz etc.) — deferred to a future project
