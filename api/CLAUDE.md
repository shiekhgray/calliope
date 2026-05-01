# API — Calliope Backend

FastAPI app in `api/app/`. Code is baked into the Docker image — rebuild required after any Python change:
```
docker compose build api && docker compose up -d api
docker compose exec api alembic upgrade head
```

## Routers (`api/app/routers/`)

| File | Endpoints |
|---|---|
| `auth.py` | POST /auth/login (OAuth2 form), /auth/refresh, GET /auth/me, POST /auth/change-password |
| `artists.py` | GET /artists (excludes VA), /artists/{id}/albums, /artists/{id}/top-tracks, /artists/{id}/compilations |
| `albums.py` | GET /albums/{id}, /albums/{id}/art, PUT /albums/{id}/art (multipart, writes Folder.jpg) |
| `tracks.py` | GET /tracks/{id}/stream (byte-range, 512KB chunks), POST /tracks/{id}/played, GET /tracks/{id}/similar |
| `genres.py` | GET /genres (accepts `?q=` for autocomplete filter) |
| `search.py` | GET /search?q= (unaccent), GET/POST /search/history (auth; upsert + prune to 10) |
| `playlists.py` | Full CRUD + add/remove/reorder tracks |
| `scanner.py` | POST /scanner/trigger (auth, 409 if running), GET /scanner/status — two phases: scan + index |
| `discover.py` | POST /discover/refresh, GET /discover/status, GET /discover(?artist_id=), POST /discover/{id}/dismiss |
| `compilations.py` | GET /compilations |
| `import_music.py` | POST /import/upload (auth; Bandcamp + Amazon zip detection + extraction) |

## Auth (`api/app/auth.py`)

- Uses `bcrypt` directly — passlib 1.7.4 is broken with bcrypt 4.x (`AttributeError on __about__`)
- Access tokens: 15 min. Refresh tokens: 30 days.
- `get_current_user` dependency used on all mutating routes + scanner trigger

## Scanner (`api/scripts/scan.py`)

Walks `Artist/Album/Track`. Fully idempotent. Never touches `play_count`.

**Critical invariants:**
- `artist_obj` resets per `album_dir` (not per `artist_dir`). If it only reset per artist_dir, a VA album with a non-"Various Artists" `albumartist` tag would corrupt `artist_obj` for subsequent albums in the same artist directory.
- `upsert_track` updates `album_id` on existing tracks. Without this, a track misassigned on first scan can never be corrected by a rescan.
- Compilation support: reads `albumartist` tag (EasyID3: `albumartist`, EasyMP4: `aART`). If set, uses it as the album's owning artist. When `albumartist != artist`, stores `track_artist` (name) + `track_artist_id` (FK) on the track.

Script must live at `api/scripts/scan.py` (inside the Docker build context). Moving it outside `api/` causes "No such file or directory" at runtime.

## Migrations

Applied: **0001–0007**. Next number: **0008**.

| File | Change |
|---|---|
| 0001_initial | All base tables |
| 0002_add_track_bitrate | `bitrate_kbps` column |
| 0003_add_play_count | `play_count INTEGER NOT NULL DEFAULT 0` |
| 0004_add_discoveries | `discoveries` table |
| 0005_add_search_history | `search_history` table + index |
| 0006_add_pgvector | vector extension, `track_vectors`, `vector_norm_params`, HNSW index |
| 0007_add_track_artist | `track_artist` + `track_artist_id` on `tracks` |
| 0008_track_credits *(planned)* | `album_artists (album_id, artist_id)`, `track_credits (track_id, artist_id)`; backfill from `track_artist_id`; drop `track_artist` + `track_artist_id` |

Alembic note: `sqlalchemy.url` in `alembic.ini` is intentionally blank — overridden at runtime via `env.py`. Do not add a value there.

## Import Format Detection (`import_music.py`)

- **Bandcamp**: flat zip + `Artist - Album.zip` filename. Strips `Artist - Album - ` prefix from track names. `cover.jpg` → `Folder.jpg`.
- **Amazon**: two-level subdirectory structure (`Artist/Album/track.mp3`). Decodes `__` → `/` in directory and file names. Copies any image file found at the album level.
- **Qobuz**: one-level subdirectory `Artist - Album/NN Title.flac`. FLACs transcoded to MP3 V0 (~245kbps) via ffmpeg subprocess. No cover art in Qobuz zips. ffmpeg is installed in the API Docker image.
- If no pattern matches, returns an error describing all three expected formats.

## Similarity Query

`GET /tracks/{id}/similar` is brute-force numpy (not pgvector ANN): fetches all vectors, z-score normalizes, L2-normalizes, dot-product. Fast enough at ~3k tracks. HNSW index exists for future use.

## Search

Uses `func.unaccent()` on both query and name/title columns — accent-insensitive search (e.g. "royksopp" finds "Röyksopp"). Requires `unaccent` PostgreSQL extension (already enabled via `CREATE EXTENSION IF NOT EXISTS unaccent`).
