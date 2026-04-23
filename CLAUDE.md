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
- **Bandcamp imports**: use the web UI at `/import` (drag-and-drop). Zips must follow `Artist - Album.zip` naming. The old `scripts/bandcamp_import.py` still works for bulk/scripted workflows.
- **Amazon Music imports**: use the web UI at `/import` (drag-and-drop). Amazon zips use a two-level subdirectory structure (`Artist/Album/track.mp3`). Amazon encodes `/` as `__` in filenames — the importer decodes these automatically. No cover art in Amazon zips; upload art via the album page afterward.
- **Import page** (`/import`): auth required; detects format automatically; shows per-file results + progress bar; auto-triggers rescan on full success. "Import Music" in the user menu.
- **`/import-music` skill**: `.claude/commands/import-music.md` — legacy CLI-based import for zips in `~/Music/`; still useful for bulk imports outside the browser

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

── added in migration 0007 (compilation albums) ──
tracks.track_artist    VARCHAR nullable — contributing artist name for compilation tracks; NULL on normal tracks
tracks.track_artist_id INTEGER nullable FK→artists — resolved artist record for track_artist
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

GET    /compilations            ← all albums owned by "Various Artists" artist; {id, title, year, cover_art_path, track_count}
GET    /artists/{id}/compilations ← compilation albums with at least one track where track_artist_id = this artist; {id, title, year, cover_art_path, artist_id, artist_name}
GET    /artists                 ← EXCLUDES "Various Artists" from results (kept in DB, just not returned)
GET    /albums/{id}             ← tracks now include track_artist (nullable str) + track_artist_id (nullable int)
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
  hooks/
    useAlbumAccent.js      ← Vibrant palette extraction + JS sRGB animation; called from Layout
    useSpacebarPlayback.js ← global spacebar handler (useSpacebarPlayback for Layout) + page first-track registration (useRegisterFirstTrack)
  player/
    PlayerContext.jsx      ← singleton Audio element; queue, play/pause, seek, volume; fires POST /tracks/{id}/played on onended; isPlaying is null (nothing loaded) | false (paused) | true (playing)
  components/
    Layout.jsx             ← top nav + player bar shell; UserMenu with Import Music link + Rescan Library + change-password modal
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
    CompilationsPage.jsx   ← /compilations; grid of VA albums; links to /albums/{id}
    ImportPage.jsx         ← /import; drag-and-drop zip upload; Bandcamp + Amazon; progress bar; auto-rescan
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
- `search.py` — GET /search?q=; GET /search/history (auth, joined across 3 entity types); POST /search/history (auth, upsert + prune to 10). Uses `func.unaccent()` on both query and name/title columns so accent-insensitive search works (e.g. "royksopp" finds "Röyksopp"). Requires `unaccent` PostgreSQL extension (already enabled: `CREATE EXTENSION IF NOT EXISTS unaccent`).
- `playlists.py` — full CRUD + add/remove/reorder; GET /{id} returns track entries with names
- `auth.py` — login, refresh, me, change-password
- `scanner.py` — POST /scanner/trigger (auth required, background task), GET /scanner/status
- `discover.py` — POST /discover/refresh (background task), GET /discover/status, GET /discover?artist_id= (optional filter), POST /discover/{id}/dismiss
- `import_music.py` — POST /import/upload (auth required); multipart upload of one or more zips; Bandcamp + Amazon format detection; synchronous extraction; returns per-file {status, artist, album, tracks_imported}

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
- Scanned result: 398 artists, 398 albums, 2748 tracks (last known good scan)
- **Bitrate**: read from `audio.info.bitrate` (bps) and stored as `bitrate_kbps` (integer kbps). WAV files may yield null — that's fine.
- **Bug fixed**: `upsert_genres` had a dead first line that set `existing_genre_ids` from `track.playlist_entries` (wrong relationship), immediately overwritten by the correct line. Was harmless on first scan (no playlist entries yet) but crashed on re-scan. Removed the dead line.
- **Compilation support**: reads `albumartist` tag (EasyID3: `albumartist`, EasyMP4: `aART`). If present, uses it as album's owning artist instead of `artist` tag. When `albumartist != artist`, stores `track_artist` (name) + `track_artist_id` (FK) on the track.
- **Critical scanner invariant**: `artist_obj` resets per `album_dir` (not per `artist_dir`). If it only reset per artist_dir, a VA album with a non-"Various Artists" albumartist tag would corrupt `artist_obj` for subsequent albums in the same directory.
- **Critical scanner invariant**: `upsert_track` updates `album_id` on existing tracks. Without this, tracks scanned under the wrong album on a first pass can never be corrected by a rescan.

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
- `web/src/player/PlayerContext.jsx` — `radioMode` (localStorage-persisted, default on), `toggleRadioMode()`, `_extendWithRadio()` fires when queue empties (via `onended`) **and** when `skipNext()` is called at end of queue; filters by sessionPlayed + seed album_id; `history` state (most-recent-first, cap 10) tracks played tracks; `queue` + `queueIndex` exposed from context
- **Bug fixed**: `skipNext()` only advanced if `next < queue.length` — at end of queue it did nothing in radio mode. Fix: `else if (radioModeRef.current) { _extendWithRadio() }` branch added.
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

### Spacebar Play/Pause (complete — browser-tested)
- `web/src/hooks/useSpacebarPlayback.js` — exports two things:
  - `useSpacebarPlayback()` — global `keydown` listener; called once from `Layout.jsx`; toggles play/pause when something is loaded (`isPlaying !== null`); calls first-track getter when nothing loaded
  - `useRegisterFirstTrack(fn)` — pages call this to register a callback that returns the page's first track; uses a module-level ref so only one registration is active at a time (cleared on unmount)
- **Architecture**: single listener in Layout handles toggle on every page; page-specific "play first track" behavior is registered via `useRegisterFirstTrack` on AlbumPage, ArtistPage, PlaylistPage. Other pages (Library, Search, Releases, etc.) get toggle-only behavior automatically.
- **`isPlaying` initial state**: changed from `false` → `null` in `PlayerContext.jsx` — `null` means nothing has ever been loaded; `false` means loaded but paused. The hook uses `isPlaying !== null` to distinguish these cases.
- **Input suppression**: spacebar does nothing when focus is on `INPUT`, `TEXTAREA`, or `contenteditable` — safe in search box, playlist rename field, change-password modal.
- **`e.preventDefault()`** called when handled — prevents page scroll.

### Track Share Links (complete — album page only)
- `web/src/pages/AlbumPage.jsx` — `ShareButton` component: hover-revealed 🔗 icon per track row; builds `{origin}/calliope/albums/{id}?play={track_id}&note={artist}_{album}`; clipboard write; "Copied!" replaces icon for 1.5s in-place (no toast)
- **`?note=` slug**: `slugify(artistName) + '_' + slugify(albumTitle)` — lowercase, non-alphanumeric → `_`, trim leading/trailing `_`. Human-readable, fully machine-ignored. Does NOT include track title.
- **Deep link handling**: `AlbumPage` reads `?play=` on load; after album data arrives, scrolls highlighted row into view (100ms timeout), attempts `playTrack()` — browser blocks autoplay on fresh load; highlighted row shows `▶ Play` inline fallback button until track becomes active
- **Highlighted row**: `.track-row--highlighted` — 3px accent left border + 8% accent background tint. Persists until the track becomes active (inline button disappears once `active` class takes over).
- **`RequireAuth` in `App.jsx`**: now encodes current `location.pathname + location.search` as `?redirect=` when redirecting unauthenticated users to `/login` — share links received while logged out land correctly after login
- **`LoginPage.jsx`**: reads `?redirect=` from `useSearchParams()`; navigates to redirect target (or `/`) after successful login
- **Playlist share links deferred**: playlist links are only useful once playlist permissions exist (otherwise anyone can browse any playlist URL already). Will add share button to `PlaylistPage` with `?note={playlist}` slug as part of the Playlist Permissions PRD.
- CSS additions: `.track-actions-group` (flex wrapper for + and 🔗), `.track-share-btn` (hidden until row hover), `.track-share-tooltip`, `.track-highlight-play-btn`, `.track-row--highlighted`. `.track-actions` width widened from 32px to 64px to fit both buttons.

### Web-Based Music Import (complete — browser-tested)
- `api/app/routers/import_music.py` — `POST /import/upload`; detects Bandcamp (flat zip + `Artist - Album.zip` filename) vs Amazon (2-level subdirectory structure); returns per-file result list
- **Bandcamp extraction**: artist/album from filename; strips `Artist - Album - ` prefix from track filenames; `cover.jpg` → `Folder.jpg`
- **Amazon extraction**: artist/album from subdirectory names; `__` → `/` decoding applied to dir and file names; also copies any image files at the album level (e.g. `Folder.jpg`)
- **Format detection**: two-level audio files → Amazon; flat audio files + ` - ` in filename stem → Bandcamp; else error with rename hint
- `web/src/pages/ImportPage.jsx` — drop zone (click or drag), per-file status rows (✓/✗/⚠/…), upload progress bar via axios `onUploadProgress`, auto-triggers rescan when all files succeed, manual "Rescan Library" button if any failed
- "Import Music" link in UserMenu popup — required adding `.user-menu-popup a` CSS rule (was previously only styled for `button` elements)
- **nginx**: `client_max_body_size 600M` + `proxy_read_timeout 120s` added to `/etc/nginx/default.d/calliope.conf` (the deployed location on this server)
- **Do not use real artist/album names for test zips** — test data writes to the actual music library; use "Test Artist / Test Album" style names

### Compilation Albums (complete — browser-tested)
- `scripts/tag_compilations.py` — host-side script; stamps `albumartist = "Various Artists"` on all tracks under `/backup/calliope/music/Various Artists/`. Run with `--dry-run` first. Requires mutagen on host (`pip3 install mutagen`).
- Per-artist duplicate dirs (e.g. `Therion/Gothic Spirits 5/`) were deleted from disk; 7 now-empty artist dirs also removed.
- Migration `0007_add_track_artist.py` applied. Scanner updated; rescan done (395 artists, 395 albums, 2701 tracks after cleanup).
- `api/app/routers/compilations.py` — new router; registered in `main.py`
- `web/src/pages/CompilationsPage.jsx` — `/compilations` route; album grid with track count
- `AlbumPage.jsx` — compilation mode: Artist column inserted between track# and title when any track has `track_artist` set
- `ArtistPage.jsx` — "Appears On" section below Albums grid; fetches `GET /artists/{id}/compilations`
- **DB cleanup completed**: 57 orphan empty albums deleted; collation version mismatch silenced (`ALTER DATABASE calliope REFRESH COLLATION VERSION`); `The Lights` artist (albumartist tag mismatch) merged into `Lights` — 34 track_artist_id refs updated, empty artist record deleted.
- **albumartist tag mismatches to watch for**: if an artist's files have `albumartist` set to a different name than their directory, the scanner will create them under the tag name. Fix by retagging the files and doing a rescan + manual DB merge if needed. Röyksopp was the known case — **resolved** (see below).
- **Röyksopp consolidation (done)**: files were split across `Royksopp/Junior/` (no umlaut, `artist` tag mismatch) and `Röyksopp/Senior/`. Fixed by: (1) moving Junior into `Röyksopp/`, (2) retagging Junior files so `artist = Röyksopp`, (3) deleting orphaned tracks + stale `Royksopp` artist from DB after rescan. `cover_art_path` also needed a manual UPDATE since the scanner matches albums by (artist_id, title), not path.
- **Moving a directory orphans its tracks in the DB**: `upsert_track` matches by `file_path`. If an artist/album dir is renamed, the scanner inserts new track records for the new paths and leaves old records behind. After any `mv`, delete orphaned tracks manually: `DELETE FROM track_genres WHERE track_id IN (SELECT id FROM tracks WHERE file_path LIKE 'OldPath/%'); DELETE FROM track_vectors WHERE ...; DELETE FROM tracks WHERE file_path LIKE 'OldPath/%';`
- **Moving a directory breaks album art**: `cover_art_path` is a relative path baked into the `albums` row. After any `mv`, update it manually: `UPDATE albums SET cover_art_path = 'NewPath/Folder.jpg' WHERE ...`

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
- **Alembic migrations applied**: `0001` through `0007` — all applied to production DB.
- **pgvector requires pgvector/pgvector:pg16 image**: stock `postgres:16` does not include the vector extension. Switched DB image to `pgvector/pgvector:pg16` — data volume persisted through the image swap without issue.
- **Collation version mismatch warning**: after switching to pgvector image, Postgres logs "collation version mismatch" (old image had glibc 2.41, new has 2.36). **Already silenced** — `ALTER DATABASE calliope REFRESH COLLATION VERSION` was run. If it reappears after a DB image upgrade, run it again.
- **Scanner router path bug**: `scanner.py` was resolving the scan script path with one too many `.parent` calls, landing at `/scripts/scan.py` instead of `/app/scripts/scan.py`. Fixed. Symptom: web UI rescan silently failed (exit code 2) while manual `docker compose exec` run worked fine.
- **Music volume is read-write**: Changed from `:ro` to `:rw` to support album art uploads writing `Folder.jpg`. This is intentional — do not revert to read-only.
- **Album art upload Content-Type**: do NOT manually set `Content-Type: multipart/form-data` on the axios PUT call — omit it entirely and let the browser set it automatically with the correct boundary. The old override was removed.
- **nginx calliope config location**: deployed at `/etc/nginx/default.d/calliope.conf` (not sites-enabled). Copy from `nginx/calliope.conf` and `sudo nginx -s reload` to apply changes.
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

- **Web-Based Music Import** (`prd/web-import.md`) — ✓ implemented; see Web-Based Music Import section above
- **Now Playing Page** (`prd/now-playing-page.md`) — ✓ implemented; `/now-playing` route; large art, wide scrubber, queue history (2 past) + up next (2 ahead) + similar tracks (5); entry via album art thumbnail in PlayerBar OR Calliope logo in nav
- **Dynamic Color Theme** (`prd/dynamic-theme.md`) — ✓ implemented; see Dynamic Color Theme section above
- **Genre Tagging** (`prd/genre-tagging.md`) — album-level genre chips on AlbumPage (writes to all tracks); three interaction modes: Fetch (Last.fm `album.getInfo`), Suggest (similarity k-NN), Add/search (autocomplete). Per-artist fetch button on ArtistPage calls `artist.getTopTags` and bulk-applies to all albums. Read-only genre preview on Releases discovery cards. Requires `LASTFM_API_KEY` in `.env`. **iTunes/Apple Music NOT used for genres** — their API returns only one broad `primaryGenreName` per item; Last.fm crowd-sourced tags are richer. Similarity suggest algorithm: walk outward until K=10 tagged neighbors found OR M=50 total checked (both configurable via query params); top 3 by frequency returned, genres already on the album excluded.
- **Spacebar Play/Pause** (`prd/spacebar-playback.md`) — ✓ implemented; see Spacebar Play/Pause section above
- **Track Share Links** (`prd/track-share-links.md`) — ✓ implemented (album page only); see Track Share Links section above
- **Playlist Permissions** (`prd/playlist-permissions.md`) — per-playlist view/edit access control; `view_mode`/`edit_mode` columns (`owner|users|everyone`) + `playlist_viewers`/`playlist_editors` join tables; gear panel in playlist detail (owner-only); `GET /playlists` becomes auth-required and filters by visibility; `GET /users` new endpoint; migration `0008` (next available). **Note**: when implementing, reassign "Ellie's playlist" to user `rose` via SQL after migration — see memory file.
- **Playlist Cards** (`prd/playlist-cards.md`) — replaces flat playlist list with rich cards; 2×2 album art collage from the 4 most "quintessential" tracks (centroid of playlist's normalized vectors, unique album_ids); first 3 track titles as preview; top 4 genre chips (empty until genre tagging ships); all data returned in `GET /playlists` (no N+1). Vector centroid algorithm is the same z-score→L2 pipeline as `/tracks/{id}/similar`.
- **Vector Expansion** (`prd/vector-expansion.md`) — expand feature vector 38→60 dims by adding chroma variance (12), tempo/BPM (1), RMS mean (1), RMS variance (1), spectral centroid mean (1), tonnetz mean (6). Breaking migration: truncate `track_vectors`, delete `vector_norm_params`, alter column to `vector(60)`, recreate HNSW index, full re-index. **Must ship before or alongside Similarity Weights.** Rename note: existing `sim_weight_dynamics` column → `sim_weight_timbral_variation` when this ships.
- **Similarity Weights** (`prd/similarity-weights.md`) — per-user 9-slider UI (0–10, default 5) in user menu ("Sound Matching"); **depends on Vector Expansion**. Full 60-dim dimension map: Tone Color (0–12), Timbral Variation (13–25), Harmonic Content (26–37), Chord Movement (38–49), Tempo (50), Loudness (51), Dynamic Range (52), Brightness (53), Tonal Character (54–59). Sliders grouped in modal: Timbre / Harmony / Rhythm & Energy. Stored as 9 integers on `users` table; applied server-side as `weight/5.0` multiplier before L2-norm. On save, invalidates `['me']` + `['similar', currentTrackId]` so Now Playing refreshes automatically.

## Development Notes

- Do not add iOS support — no Apple devices in use
- Metadata enrichment (MusicBrainz etc.) is deferred to a future project
- Transcoding is out of scope — serve files as-is
- No browser offline support required
- Scanner lives in `api/scripts/` and can also be triggered via the web UI (user menu → Rescan Library)
- **Project tracking**: `.todo` is a lean PRD index. Full specs live in `prd/`. Use `/coffee` at session start to load context from `.todo` + relevant PRDs.
- **Expert agents**: use `/api`, `/web`, `/android`, `/similarity` when working in those subsystems — each loads its own file context at invocation
