# Calliope 2

A personal music streaming service — the spiritual successor to an older single-file PHP app.
Supports two users (owner + wife), playlist management, genre tagging, and album art display.
Designed for home server deployment with a native Android app including Android Auto support.

## Architecture Overview

```
calliope/
  api/              ← FastAPI (Python), runs in Docker
    scripts/        ← scan.py and seed_users.py live here (inside build context)
  indexer/          ← Similarity engine; separate Docker container (built, not yet deployed)
    app/
      main.py       ← plain Python stdlib HTTP server; POST /index + GET /status
      index.py      ← MFCC/chroma feature extraction + pgvector upsert + norm param recompute
      config.py     ← DATABASE_URL, MUSIC_ROOT from env
      database.py
      models.py     ← TrackVector + VectorNormParams only
    Dockerfile      ← python:3.12-slim + libsndfile1 + ffmpeg + librosa
    requirements.txt
  web/              ← React + Vite, runs as Docker container (dev server)
  android/          ← Kotlin + Jetpack Compose (not yet started)
  nginx/            ← nginx config snippets
  scripts/          ← host-side utility scripts (bandcamp_import.py)
  prd/              ← PRD files, one per feature/phase
  .claude/commands/ ← custom slash commands (expert agents + workflows)
  docker-compose.yml
  README.md         ← operator reference (DB access, useful queries, commands)
  CLAUDE.md
  .todo             ← lean index of PRDs (done / up next / later)
```

## Tech Stack

| Layer       | Technology                              |
|-------------|------------------------------------------|
| API         | Python, FastAPI, uvicorn                |
| Indexer     | Python stdlib HTTP server, librosa, numpy, pgvector (separate container) |
| Database    | PostgreSQL 16                           |
| Migrations  | Alembic                                 |
| ORM         | SQLAlchemy                              |
| Auth        | JWT (python-jose + bcrypt)              |
| Audio tags  | Mutagen                                 |
| Web         | React, Vite, React Router, React Query, node-vibrant v4 |
| Similarity  | librosa, numpy, pgvector — indexer container + API numpy query |
| Android     | Kotlin, Jetpack Compose, Media3/ExoPlayer |
| Containers  | Docker Compose (API + PostgreSQL + Web + Indexer) |
| Proxy       | Nginx (existing, extended)              |

## Infrastructure

- **Home server**: Linux, i7, plenty of RAM, SSD + magnetic RAID
- **API container**: Ubuntu LTS base image
- **DB container**: `pgvector/pgvector:pg16` image (NOT stock postgres:16 — stock image lacks the vector extension needed for similarity engine)
- **Web container**: node:22-slim, runs Vite dev server on port 5173
- **Music files**: `/backup/calliope/music/` — mounted **read-write** into the API container (needed for album art uploads writing `Folder.jpg`)
- **Nginx**: Already running for other services (wiki). Calliope proxied alongside it.
- **Public URL**: `https://dresdengray.com/calliope/` — nginx proxies `/calliope/api/` → port 8000, `/calliope` → port 5173 (Vite). HTTPS via Let's Encrypt, auto-renewing.
- **Home DNS**: `dresdengray.com` — Vite `allowedHosts` includes this so the dev server accepts requests from it.

## Users

Two users seeded via `api/scripts/seed_users.py`:
- id=1 (owner)
- id=2 `thefacesblur` — seeded with temporary password, should be changed via change-password
- id=3 `clippy` / `Tr0mb0ne!` — **test user for development/smoke testing** (use this instead of the owner account)

## Music Library

- Location: `/backup/calliope/music/`
- Structure: `Artist/Album/Track.mp3`
- ~255 artists, ~2500 audio files
- Formats: MP3 (primary), M4A, WAV — all must be handled
- **Album art**: stored as files in album directories, NOT embedded in ID3 tags
  - Priority order: `Folder.jpg` → `AlbumArt*_Large.jpg` → first `.jpg` found in directory
  - Art can be uploaded via the web UI (hover album art on album page) — writes `Folder.jpg` to the album dir
- Duplicate tracks (same track as both .mp3 and .m4a) exist — leave them alone, do not deduplicate
- Non-audio noise files present: `desktop.ini`, `.DS_Store`, `.db` — scanner must ignore these
- **Adding music**: drop files into the directory structure, then use "Rescan Library" in the web UI user menu
- **Bandcamp imports**: use `scripts/bandcamp_import.py` (runs on the host, not in Docker). See `prd/bandcamp-import.md`. Format: `Artist - Album.zip`. Dry-run with `--dry-run`. After import, trigger a rescan.
- **Amazon Music imports**: download zips land in `~/Music/<date>/`. Use `/import-music` skill to extract and rescan. Amazon encodes `/` as `__` in filenames (e.g. `start__end.mp3`) — the ID3 tags usually have the correct title; verify in the browser after import.
- **Import staging dir**: `~/Music/` — drop Amazon zips or loose Artist/Album dirs here, then run `/import-music`
- **`/import-music` skill**: `.claude/commands/import-music.md` — inventories `~/Music/`, checks for duplicates, extracts zips, copies loose dirs, runs scanner, reports counts, offers cleanup

## Database Schema

```
users              id, username, password_hash
artists            id, name
albums             id, artist_id, title, year, cover_art_path
tracks             id, album_id, title, track_number, duration_ms, bitrate_kbps, file_path, format, play_count
genres             id, name
track_genres       track_id, genre_id
playlists          id, owner_id, title, description, created_at
playlist_tracks    id, playlist_id, track_id, position
discoveries        id, artist_id, itunes_collection_id (unique bigint), album_title, release_date, artwork_url, dismissed, first_seen_at
search_history     id, user_id, entity_type ('artist'|'album'|'track'), entity_id, visited_at; UNIQUE(user_id, entity_type, entity_id)

── added in migration 0006 (similarity engine) ──
track_vectors      track_id (FK unique), feature_vector vector(38), file_mtime bigint
vector_norm_params id (always 1), means float[38], stds float[38], updated_at
```

`cover_art_path` is a relative path from the music root to the cover image.
Album art is served through the API — no direct filesystem exposure to clients.

`play_count` is `INTEGER NOT NULL DEFAULT 0`. The scanner never touches it — safe to rescan without losing play history.

## API Design

- Byte-range streaming is required on the stream endpoint (enables seeking in HTML5 Audio and ExoPlayer)
- Auth uses short-lived access tokens (15 min) + long-lived refresh tokens (30 days)
- Two users stored in the `users` table — no external identity provider

### Key Endpoints (as built)

```
POST   /auth/login
POST   /auth/refresh
GET    /auth/me                 ← returns {id, username} for current session
POST   /auth/change-password    ← requires {current_password, new_password} (min 8 chars)

GET    /artists
GET    /artists/{id}/albums     ← returns {id, title, year, cover_art_path, artist_id, artist_name}
GET    /artists/{id}/top-tracks ← top 10 by play_count DESC, ties broken by RANDOM(); always returns tracks
GET    /albums/{id}             ← returns album + tracks[] (includes play_count) + artist_name
GET    /albums/{id}/art         ← serves cover image with cache headers
PUT    /albums/{id}/art         ← auth required; multipart image upload; writes Folder.jpg to album dir
GET    /tracks/{id}/stream      ← byte-range streaming
POST   /tracks/{id}/played      ← auth required; increments play_count; returns {play_count}

GET    /genres
GET    /search?q=               ← returns {artists, albums, tracks} — both albums and tracks include artist_id, artist_name; albums also include year, cover_art_path

GET    /search/history          ← auth required; returns current user's 10 most recent history entries
POST   /search/history          ← auth required; upserts a visit (entity_type, entity_id); prunes to 10

GET    /playlists
GET    /playlists/{id}          ← returns playlist + entries[]{id, position, track{...+album_id, album_title, artist_id, artist_name}}
POST   /playlists               ← auth required
PUT    /playlists/{id}          ← auth required
DELETE /playlists/{id}          ← auth required
POST   /playlists/{id}/tracks   ← auth required
DELETE /playlists/{id}/tracks/{track_id}  ← auth required
PUT    /playlists/{id}/tracks/reorder     ← auth required

POST   /scanner/trigger         ← auth required, 409 if already running
GET    /scanner/status

POST   /discover/refresh        ← auth required, 409 if already running; background task
GET    /discover/status         ← {running, last_refreshed}
GET    /discover                ← non-dismissed discoveries not already in library (filtered by artist+title); optional ?artist_id= to scope to one artist
POST   /discover/{id}/dismiss   ← auth required; sets dismissed=true permanently
```

**Important**: Several endpoints return explicit dicts (not raw SQLAlchemy models) to include
joined fields like `artist_name`, `album_title`. Do not change these back to raw model returns.

## Web App (`web/`)

Built with React + Vite. Runs as a Docker container (dev server). `./web/src` is volume-mounted
for HMR — edit files on the host and changes appear in the browser immediately.

### Structure

```
web/src/
  api/client.js           ← axios instance; attaches Bearer token; auto-refreshes on 401
  auth/
    AuthContext.jsx        ← loggedIn, username, login(), logout(); username stored in localStorage
    LoginPage.jsx
  player/
    PlayerContext.jsx      ← singleton Audio element; queue, play/pause, seek, volume; fires POST /tracks/{id}/played on onended
  components/
    Layout.jsx             ← top nav + player bar shell; UserMenu with change-password modal + Rescan Library
    PlayerBar.jsx          ← fixed bottom bar; volume popover; album/artist links
    AddToPlaylistMenu.jsx  ← "+" popover on every track row
    ChangePasswordModal.jsx
  pages/
    LibraryPage.jsx        ← artist list
    ArtistPage.jsx         ← top 10 tracks section + albums grid
    AlbumPage.jsx          ← album header (with art upload overlay) + track table
    SearchPage.jsx
    PlaylistsPage.jsx      ← list + create/delete
    PlaylistPage.jsx       ← playlist detail + remove tracks
    ReleasesPage.jsx       ← iTunes-powered new release discovery; refresh button; dismiss per card
    NowPlayingPage.jsx     ← /now-playing; large art + scrubber + controls + queue context + similar tracks
```

### Key conventions

- **Track enrichment**: when passing a track to `playTrack()`, always include `album_id`,
  `album_title`, `artist_id`, `artist_name` — the PlayerBar uses these for links. Forgetting
  any of them causes the link to silently disappear (by design — no fallback text).
- **Vite proxy**: `/calliope/api` → `process.env.API_URL || http://localhost:8000` (strips `/calliope/api` prefix).
  In Docker, `API_URL=http://api:8000` is set via compose env. For local dev outside Docker,
  the default `localhost:8000` works if the API container port is exposed.
- **Hardcoded API URLs**: any URL not going through the axios `api` client (e.g. `<img src>`, `audio.src`, direct `axios.post`) must use the `/calliope/api/` prefix — not `/api/`. The axios client already has `baseURL: '/calliope/api'`. Forgetting this on hardcoded paths causes silent failures (images don't load, audio doesn't play, login fails).
- **Username recovery**: `AuthContext` calls `GET /auth/me` on load if a token exists but
  username is missing from localStorage (handles pre-existing sessions).
- **Play count**: `onended` fires only on natural completion (not skip). `POST /tracks/{id}/played`
  is called fire-and-forget (errors silently swallowed — a missed count is acceptable).
- **Top tracks on artist page**: always shown (no hide-if-empty). Zero-play ties broken by
  `RANDOM()` so the initial list is shuffled. Played tracks bubble up naturally over time.
- **Album art upload**: hover overlay on the album art large image. Writes `Folder.jpg` to the
  album directory on disk. Cache-busts the displayed image with a `?v=N` query param after upload.
  The `?v=` param is local React state — the art endpoint itself has long cache headers.
- **Rescan Library**: in the user menu dropdown. Polls `/scanner/status` every 2s. Handles 409
  (already running) gracefully. Shows "Scan complete" in accent color for 3s then resets to idle.
- **Releases page** (`/releases`): polls `/discover/status` every 2s during refresh. Dismiss is permanent — dismissed entries survive subsequent refreshes (flag is never reset). Albums that appear in the library after a rescan are automatically filtered out at query time (no manual cleanup needed). iTunes returns artwork at 100x100; upscaled to 300x300 by replacing the URL suffix.

## Android App

- Kotlin + Jetpack Compose
- Media3/ExoPlayer for playback
- `MediaBrowserServiceCompat` for Android Auto integration
- `WorkManager` for background playlist downloads
- `Room` for local downloaded playlist state
- `EncryptedSharedPreferences` for JWT token storage
- WiFi guard: warn before streaming/downloading on cellular, offer override (session-scoped)
- Distribution: APK sideload initially, Play Store later ($25 one-time fee)

## What Has Been Built

### Infrastructure (Phase 1 — complete)
- `docker-compose.yml` — pgvector/pgvector:pg16 + api + web + indexer; `version:` header is obsolete in Compose v2 but left in place
- `api/Dockerfile` — Ubuntu 24.04, Python venv at `/venv`
- `web/Dockerfile` — node:22-slim, runs `npm run dev`; src volume-mounted for HMR
- `nginx/calliope.conf` — drop-in location block, proxy_buffering off, proxy_force_ranges on
- `.env.example` — template; real `.env` has dev credentials (not committed)
- `README.md` — operator reference: DB access, useful psql queries, docker compose commands

### API (Phase 2 — complete and smoke-tested)
- `api/app/main.py` — FastAPI entry point, all routers registered, `/health` endpoint
- `api/app/config.py` — pydantic-settings reads `DATABASE_URL`, `SECRET_KEY`, `MUSIC_ROOT` from env
- `api/app/database.py` — SQLAlchemy engine + `get_db` dependency
- `api/app/models.py` — all 8 models with relationships; Track has `play_count` column; SearchHistory added
- `api/alembic/` — Alembic configured; `DATABASE_URL` injected from env (not stored in alembic.ini)
- `api/alembic/versions/0001_initial.py` — all 8 tables + indexes
- `api/alembic/versions/0002_add_track_bitrate.py` — bitrate_kbps column
- `api/alembic/versions/0003_add_play_count.py` — play_count INTEGER NOT NULL DEFAULT 0
- `api/alembic/versions/0004_add_discoveries.py` — discoveries table (iTunes release tracking)
- `api/alembic/versions/0005_add_search_history.py` — search_history table + index

### Routers (all in `api/app/routers/`)
- `artists.py` — GET /artists, GET /artists/{id}/albums, GET /artists/{id}/top-tracks
- `albums.py` — GET /albums/{id} (tracks include play_count), GET /albums/{id}/art, PUT /albums/{id}/art
- `tracks.py` — GET /tracks/{id}/stream (full byte-range support, 512KB chunks), POST /tracks/{id}/played
- `genres.py` — GET /genres
- `search.py` — GET /search?q=; GET /search/history (auth, joined across 3 entity types); POST /search/history (auth, upsert + prune to 10)
- `playlists.py` — full CRUD + add/remove/reorder; GET /{id} returns track entries with names
- `auth.py` — login, refresh, me, change-password
- `scanner.py` — POST /scanner/trigger (auth required, background task), GET /scanner/status
- `discover.py` — POST /discover/refresh (background task), GET /discover/status, GET /discover?artist_id= (optional filter), POST /discover/{id}/dismiss

### Auth (`api/app/auth.py`)
- Uses `bcrypt` directly (NOT passlib — passlib 1.7.4 is broken with bcrypt 4.x)
- `get_current_user` dependency used on all mutating routes + scanner trigger
- `hash_password`, `verify_password`, `create_access_token`, `create_refresh_token`

### Scripts
- `api/scripts/scan.py` — library scanner (run: `docker compose exec api python scripts/scan.py`)
- `api/scripts/seed_users.py` — add users: `docker compose exec api python scripts/seed_users.py <user> <pass>`
- `scripts/bandcamp_import.py` — host-side Bandcamp zip importer. Run: `python3 scripts/bandcamp_import.py file.zip`. Use `--dry-run` to preview. Zips must follow Bandcamp's `Artist - Album.zip` naming convention.

### Scanner (`api/scripts/scan.py`)
- Walks `Artist/Album/Track` structure; falls back to directory names if tags missing
- Mutagen easy-tag interface for MP3/M4A/WAV
- Cover art priority: `Folder.jpg` → `AlbumArt*_Large.jpg` → first `.jpg`
- Fully idempotent — safe to re-run; refreshes year/cover/duration/bitrate if previously missing
- **Does NOT touch play_count** — rescan is safe, play history is preserved
- Genres upserted from ID3/M4A genre tags, no duplicates
- Progress logged every 100 tracks
- Scanned result: 253 artists, 410 albums, 2717 tracks (after EDEN "vertigo" + "Dark" import)
- **Bitrate**: read from `audio.info.bitrate` (bps) and stored as `bitrate_kbps` (integer kbps). WAV files may yield null — that's fine.
- **Bug fixed**: `upsert_genres` had a dead first line that set `existing_genre_ids` from `track.playlist_entries` (wrong relationship), immediately overwritten by the correct line. Was harmless on first scan (no playlist entries yet) but crashed on re-scan. Removed the dead line.

### Web App (Phase 4 — complete)
- See `web/` structure above
- Dark theme, default purple accent (#a855f7) — dynamically overridden per current track (see Dynamic Color Theme below)
- Track rows show `bitrate_kbps` in a muted right-aligned column (`.track-bitrate` in index.css)
- Track rows show `play_count` in a muted right-aligned column (`.track-play-count`); blank when 0
- Playlist drag-and-drop reorder: native HTML5 DnD; optimistic local state via `localTracks` useState; fires `PUT /playlists/{id}/tracks/reorder`; reverts on API error
- Genre tagging UI deferred to Phase 6. Nginx static build config deferred indefinitely — dev server is sufficient.

### Search Enhancements (complete)
- Search results: albums now return `artist_id`, `artist_name` (explicit dict, not raw model)
- `SearchPage.jsx`: album cards show artist name as a link; track rows show `Artist — Album` links below the title

### Search History (complete — browser-tested)
- Migration `0005_add_search_history.py` applied to production DB
- `SearchHistory` model in `models.py` — UNIQUE(user_id, entity_type, entity_id)
- `GET /search/history` — auth required; fetches top 10 newest entries; resolves names via separate per-type queries merged in Python; orphaned entries (deleted library items) silently omitted
- `POST /search/history` — auth required; upserts visited_at on duplicate; prunes to 10 rows after every write
- `SearchPage.jsx` — `SearchHistory` component renders a chip grid above the search form when logged in and history is non-empty; artist/album clicks navigate + record; track clicks play + record (fire-and-forget, errors swallowed); invalidates `['search-history']` React Query key after every click
- CSS: `.search-history-section`, `.search-history-label`, `.search-history-grid`, `.search-history-chip` in `index.css`
- **Login endpoint uses OAuth2 form encoding** — `POST /auth/login` takes `application/x-www-form-urlencoded` (`username=`/`password=` fields), NOT JSON. Use `-d 'username=X&password=Y'` in curl, not `-H 'Content-Type: application/json'`.

### Releases Discovery (complete)
- `web/src/pages/ReleasesPage.jsx` — `/releases` route, added to top nav
- `api/app/routers/discover.py` — iTunes Search API integration; background refresh task
- `api/app/models.py` — `Discovery` model added
- Migration `0004_add_discoveries.py` applied to production DB
- iTunes rate: ~6 req/s (150ms sleep between artists). Strips " - Single" / " - EP" suffixes from iTunes album titles.
- Dismiss is permanent per entry; refreshes never reset dismissed flag; owned albums auto-filtered at query time

### Releases Filters (complete)
- `web/src/pages/ReleasesPage.jsx` — client-side text filter (artist or album name) + sort dropdown (Artist A–Z, Newest, Oldest)
- `web/src/index.css` — `.releases-controls`, `.releases-filter-input`, `.releases-count` added
- No API changes — full list already fetched; filtering/sorting done with `useMemo`
- "Showing X of Y" count only shown when a filter is active

### Artist Missing Releases (complete)
- `web/src/pages/ArtistPage.jsx` — "Missing Releases" section added below the album grid; only renders when non-empty; reuses `.releases-grid` / `.release-card` CSS
- `api/app/routers/discover.py` — `GET /discover` now accepts optional `?artist_id=` query param to filter to one artist
- Dismiss from artist page invalidates both `['discoveries', 'artist', id]` and global `['discoveries']` so the Releases page stays in sync
- Dismiss button only shown when `loggedIn` (uses `useAuth()`)

### Similarity Engine + Radio Mode (deployed and indexing)
- `indexer/` — separate Docker container; python:3.12-slim + libsndfile1 + ffmpeg; librosa==0.10.2, numpy==1.26.4, pgvector==0.3.6
- `indexer/app/main.py` — plain Python stdlib HTTP server on port 8001; `POST /index` (202/409), `GET /status` (`{running, indexed, to_index}`)
- `indexer/app/index.py` — `extract_features()`: loads first 60s via librosa, returns 38-dim vector (13 MFCC mean + 13 MFCC var + 12 chroma mean); `run_indexing()`: incremental by file mtime; recomputes z-score norm params after batch
- `api/alembic/versions/0006_add_pgvector.py` — enables vector extension, creates track_vectors + vector_norm_params + HNSW cosine index. **Applied to production DB.**
- `api/app/models.py` — `TrackVector` + `VectorNormParams` models added
- `api/requirements.txt` — added numpy==1.26.4, pgvector==0.3.6
- `api/app/routers/tracks.py` — `GET /tracks/{id}/similar?limit=25` (auth required): fetches all vectors, z-score normalizes + L2-normalizes in numpy, returns cosine-similar tracks; 404 if track not yet indexed
- `api/app/routers/scanner.py` — now has two phases: "scanning" (scan.py subprocess) + "indexing" (calls indexer via urllib, polls until done); `/scanner/status` proxies `{indexed, to_index}` from indexer when phase=="indexing"
- `web/src/player/PlayerContext.jsx` — `radioMode` (localStorage-persisted, default on), `toggleRadioMode()`, `_extendWithRadio()` fires when queue empties; filters by sessionPlayed + seed album_id; `history` state (most-recent-first, cap 10) tracks played tracks; `queue` + `queueIndex` exposed from context
- `web/src/components/PlayerBar.jsx` — `≋` radio toggle button (accent when on); album art thumbnail (48×48) links to `/now-playing`; player-bar grid is `auto 1fr auto 1fr`
- **Indexing speed**: much faster than estimated ~2s/track in practice; 388+ tracks indexed within minutes of first run
- **Similarity query is brute-force numpy** (not pgvector ANN) — fetches all ~3k vectors, normalizes, dot-product. Fast enough at this scale; HNSW index is forward-looking.

### Now Playing Page (complete — browser-tested)
- `web/src/pages/NowPlayingPage.jsx` — route `/now-playing`, nested inside Layout (PlayerBar still visible)
- Two-column grid layout: left = art + controls, right = queue context
- **Left column**: large album art (`40vmin` square), track title, artist·album·year meta (year from `GET /albums/{id}` React Query — usually cached), wide scrubber, ⏮⏪⏯⏩⏭ controls (⏪/⏩ = ±15s), horizontal volume slider, radio toggle
- **Right column sections**: Played (2 past tracks oldest-first, link to album page), Now Playing (animated equalizer + accent color), Up Next (2 ahead; if radio on and <2 in queue, shows "Radio will continue…" placeholders), Similar (5 tracks via `/tracks/{id}/similar?limit=5`; hidden entirely if track not indexed)
- **PlayerContext additions**: `history` state array (most-recent-first, capped at 10); pushed on `onended` and `skipNext`; reset on `playTrack`; `queue` + `queueIndex` now exposed from context value
- **PlayerBar**: album art thumbnail added as first grid column (`auto 1fr auto 1fr`); thumbnail links to `/now-playing`; `onError` hides broken image
- **Layout**: "Calliope" nav brand is now a `<Link to="/now-playing">` (was a plain `<span>`)
- **Equalizer animation**: `.np-equalizer` — 3 bars, CSS `@keyframes np-eq` scaleY animation with staggered delays
- **Similar section**: uses React Query key `['similar', trackId]`; disabled when no currentTrack; hidden (not placeholder) when track not yet indexed (API returns 404, query returns null/empty)

### Dynamic Color Theme (complete — browser-tested)
- `web/src/hooks/useAlbumAccent.js` — called from `Layout.jsx`; extracts Vibrant palette from current track's album art URL; derives three accent tiers; animates via `requestAnimationFrame`
- `node-vibrant` v4 installed (`import { Vibrant } from 'node-vibrant/browser'`). In `package.json` and in the container's `node_modules`.
- **Three dynamic CSS variables** (all animated together in sRGB):
  - `--accent` — main accent; Vibrant hue at `baseL` (pinned 0.52–0.72); used for page titles (`.page h2`, `.page-header h2`), player album/artist links, general UI
  - `--accent-hover` — lighter tier (`baseL + 0.22`, max 0.92); used for hover states
  - `--accent2` — darker tier (`baseL - 0.22`, min 0.40); used for `.nav-brand` (Calliope logo)
  - `--accent-dim` — `--accent` hex + `33` (20% alpha suffix); set alongside `--accent`
- **Fallbacks**: `--accent` → `#a855f7`, `--accent-hover` → `#c084fc`, `--accent2` → `#7e22ce`
- **Animation**: JS `requestAnimationFrame` loop, ease-in-out, 500ms, sRGB linear interpolation. Cancellation flag prevents stale Vibrant responses from stomping a newer animation.
- **Why not CSS `@property` + transition**: Chromium interpolates `@property` `<color>` values in OKLab by default; transitions between high-chroma complementary colors pass through a washed-out near-white midpoint. sRGB interpolation in JS avoids this entirely.
- **Art element flash fix**: `.np-art` and `.player-art-thumb` have `background: var(--surface2)` — unloaded images show dark grey instead of browser-default white.

## Infrastructure Gotchas

- **Docker version**: Upgraded to Docker CE 20.10 + Compose v2 (plugin). Use `docker compose` (space, not hyphen). The `version:` header in docker-compose.yml is now obsolete and ignored — harmless warning.
- **Docker storage driver**: `/etc/docker/daemon.json` explicitly sets `overlay2` — needed because the old Docker 19.03 left behind devicemapper dirs that confused the new daemon. Do not remove this file.
- **buildx**: Manually installed at `~/.docker/cli-plugins/docker-buildx` (v0.33.0). Not in PATH as a standalone binary — only accessible via `docker buildx`.
- **Alembic migrations**: Run manually after first boot: `docker compose exec api alembic upgrade head`
- **alembic.ini**: The default Alembic template includes a duplicate `sqlalchemy.url` line (line 89). This was removed — `sqlalchemy.url` appears only once (blank, at line 10) and is overridden at runtime via `env.py`.
- **passlib dropped**: passlib 1.7.4 is incompatible with bcrypt 4.x (AttributeError on `__about__`). Replaced with direct `bcrypt` calls in `api/app/auth.py`.
- **Node.js**: Server has Node 14 system install. nvm is installed; use `nvm use 22` (LTS). Web container uses node:22-slim so Docker builds are unaffected.
- **scan.py location**: Must live at `api/scripts/scan.py` (inside the Docker build context). Moving it outside `api/` will cause "No such file or directory" errors at runtime.
- **API container requires rebuild for code changes**: `api/` is baked into the image, not volume-mounted (only music files are). After changing any Python file or migration, run `docker compose build api && docker compose up -d api`. Migrations must be applied separately after restart: `docker compose exec api alembic upgrade head`.
- **Alembic migrations applied**: `0001` through `0006` — all applied to production DB.
- **pgvector requires pgvector/pgvector:pg16 image**: stock `postgres:16` does not include the vector extension. Switched DB image to `pgvector/pgvector:pg16` — data volume persisted through the image swap without issue.
- **Collation version mismatch warning**: after switching to pgvector image, Postgres logs "collation version mismatch" (old image had glibc 2.41, new has 2.36). Cosmetic only — does not affect functionality. Can be silenced with `ALTER DATABASE calliope REFRESH COLLATION VERSION` if desired.
- **Scanner router path bug**: `scanner.py` was resolving the scan script path with one too many `.parent` calls, landing at `/scripts/scan.py` instead of `/app/scripts/scan.py`. Fixed. Symptom: web UI rescan silently failed (exit code 2) while manual `docker compose exec` run worked fine.
- **Music volume is read-write**: Changed from `:ro` to `:rw` to support album art uploads writing `Folder.jpg`. This is intentional — do not revert to read-only.
- **Album art upload Content-Type**: do NOT manually set `Content-Type: multipart/form-data` on the axios PUT call — omit it entirely and let the browser set it automatically with the correct boundary. The old override was removed.
- **`/calliope/` path move**: service moved from root to `/calliope/` subpath. Several hardcoded `/api/` URLs in the frontend had to be updated to `/calliope/api/`. Files affected: `AlbumPage.jsx` (img src + audio upload), `ArtistPage.jsx` (img src), `SearchPage.jsx` (img src), `PlayerContext.jsx` (audio.src), `AuthContext.jsx` (login POST).

## Expert Agent Slash Commands (`.claude/commands/`)

Four subsystem expert agents, each loading its codebase at invocation time:

- `/api` — FastAPI backend: all endpoints, models, migrations, auth, scanner, Docker workflow
- `/web` — React frontend: all pages, PlayerContext/AuthContext APIs, CSS vars, React Query keys, conventions
- `/android` — Kotlin/Compose/ExoPlayer: architecture, API contract, not yet coded
- `/similarity` — MFCC/chroma pipeline, pgvector schema, incremental indexing, radio mode design

Also:
- `/import-music` — import Amazon/Bandcamp zips from `~/Music/` staging area
- `/coffee` — load session context at start
- `/beer` — save session state before context clear

## Planned Features (PRDs written, not yet implemented)

- **Web-Based Music Import** (`prd/web-import.md`) — drag-and-drop zip upload at `/import`; Bandcamp (`Artist - Album.zip`, flat zip) and Amazon (two-level subdirectory, `__` encodes `/`) formats auto-detected; synchronous upload (no background task); auto-triggers rescan on success. nginx needs `client_max_body_size 600M` + `proxy_read_timeout 120s`. `scripts/bandcamp_import.py` is NOT removed.
- **Now Playing Page** (`prd/now-playing-page.md`) — ✓ implemented; `/now-playing` route; large art, wide scrubber, queue history (2 past) + up next (2 ahead) + similar tracks (5); entry via album art thumbnail in PlayerBar OR Calliope logo in nav
- **Dynamic Color Theme** (`prd/dynamic-theme.md`) — ✓ implemented; see Dynamic Color Theme section above
- **Spacebar Play/Pause** (`prd/spacebar-playback.md`) — global keydown handler; suppressed in inputs; plays first track on album/artist/playlist pages if nothing loaded
- **Track Share Links** (`prd/track-share-links.md`) — deep links `/albums/{id}?play={track_id}` and `/playlists/{id}?play={track_id}`; auth redirect via `?redirect=` on login; track row highlight + inline play button on landing

## Development Notes

- Do not add iOS support — no Apple devices in use
- Metadata enrichment (MusicBrainz etc.) is deferred to a future project
- Transcoding is out of scope — serve files as-is
- No browser offline support required
- Scanner lives in `api/scripts/` and can also be triggered via the web UI (user menu → Rescan Library)
- **Project tracking**: `.todo` is a lean PRD index. Full specs live in `prd/`. Use `/coffee` at session start to load context from `.todo` + relevant PRDs.
- **Expert agents**: use `/api`, `/web`, `/android`, `/similarity` when working in those subsystems — each loads its own file context at invocation
