# API — Calliope Backend

FastAPI app in `api/app/`. Code is baked into the Docker image — rebuild required after any Python change:
```
docker compose build api && docker compose up -d api
docker compose exec api alembic upgrade head
```

## Routers (`api/app/routers/`)

| File | Endpoints |
|---|---|
| `auth.py` | POST /auth/login (OAuth2 form), /auth/refresh, GET /auth/me, POST /auth/change-password, PUT /auth/similarity-weights (partial update, 0–10 per field) |
| `artists.py` | GET /artists (excludes VA), /artists/{id}/albums (album_type='album' only), /artists/{id}/singles (album_type IN ('single','ep'), includes first_track), /artists/{id}/top-tracks?limit=N (default 25, uses album_artists join), /artists/{id}/compilations, /artists/{id}/genres/fetch (Last.fm artist.getTopTags) |
| `albums.py` | GET /albums/{id} (includes album_type), /albums/{id}/art, PUT /albums/{id}/art (multipart, writes Folder.jpg), PATCH /albums/{id}/type (owner-only, validates album/ep/single); GET /albums/{id}/genres, GET /albums/{id}/genres/fetch (Last.fm), GET /albums/{id}/genres/suggest (similarity k-NN), POST /albums/{id}/genres (auth, both users), DELETE /albums/{id}/genres/{genre_id} (auth, both users) |
| `tracks.py` | GET /tracks?sort=play_count&limit=N (auth, default 50), GET /tracks/{id}/stream (byte-range, 512KB chunks), POST /tracks/{id}/played, GET /tracks/{id}/similar (applies per-user sim_weight_* via DIM_SLICES) |
| `genres.py` | GET /genres (accepts `?q=` for autocomplete filter, limit 20 when q set) |
| `search.py` | GET /search?q= (unaccent), GET/POST /search/history (auth; upsert + prune to 10) |
| `playlists.py` | Full CRUD + add/remove/reorder tracks |
| `scanner.py` | POST /scanner/trigger (auth, 409 if running), GET /scanner/status — two phases: scan + index |
| `discover.py` | POST /discover/refresh, GET /discover/status, GET /discover(?artist_id=), POST /discover/{id}/dismiss, GET /discover/{id}/genres/fetch (Last.fm album.getInfo; read-only, nothing persisted) |
| `compilations.py` | GET /compilations |
| `import_music.py` | POST /import/upload (auth; Bandcamp + Amazon zip detection + extraction) |
| `credits.py` | GET /albums/{id}/artists, POST /albums/{id}/artists, DELETE /albums/{id}/artists/{artist_id}, POST /tracks/{id}/credits, DELETE /tracks/{id}/credits/{artist_id} — all mutating endpoints owner-only (user_id == 1) |

## Auth (`api/app/auth.py`)

- Uses `bcrypt` directly — passlib 1.7.4 is broken with bcrypt 4.x (`AttributeError on __about__`)
- Access tokens: 15 min. Refresh tokens: 30 days.
- `get_current_user` dependency used on all mutating routes + scanner trigger

## Scanner (`api/scripts/scan.py`)

Walks `Artist/Album/Track`. Fully idempotent. Never touches `play_count`.

**Critical invariants:**
- `artist_obj` resets per `album_dir` (not per `artist_dir`). If it only reset per artist_dir, a VA album with a non-"Various Artists" `albumartist` tag would corrupt `artist_obj` for subsequent albums in the same artist directory.
- `upsert_track` updates `album_id` on existing tracks. Without this, a track misassigned on first scan can never be corrected by a rescan.
- Compilation support: reads `albumartist` tag (EasyID3: `albumartist`, EasyMP4: `aART`). If set, uses it as the album's owning artist. The scanner no longer writes `track_artist`/`track_artist_id` — those columns were dropped in migration 0008. Credits are managed manually via the credits API.

Script must live at `api/scripts/scan.py` (inside the Docker build context). Moving it outside `api/` causes "No such file or directory" at runtime.

## Migrations

Applied: **0001–0011**. Next number: **0012**.

| File | Change |
|---|---|
| 0001_initial | All base tables |
| 0002_add_track_bitrate | `bitrate_kbps` column |
| 0003_add_play_count | `play_count INTEGER NOT NULL DEFAULT 0` |
| 0004_add_discoveries | `discoveries` table |
| 0005_add_search_history | `search_history` table + index |
| 0006_add_pgvector | vector extension, `track_vectors`, `vector_norm_params`, HNSW index |
| 0007_add_track_artist | `track_artist` + `track_artist_id` on `tracks` |
| 0008_track_credits | `album_artists (album_id, artist_id)`, `track_credits (track_id, artist_id)`; backfill from existing `track_artist_id`; drop `track_artist` + `track_artist_id` |
| 0009_add_album_type | `album_type VARCHAR(8) NOT NULL DEFAULT 'album'` on `albums` |
| 0010_vector_expansion | Drops HNSW, truncates `track_vectors` + `vector_norm_params`, alters `feature_vector` to `vector(60)`, recreates HNSW |
| 0011_add_similarity_weights | 9 `sim_weight_*` columns on `users` (INTEGER NOT NULL DEFAULT 5): timbre, timbral_variation, harmony, chord_movement, tempo, loudness, dynamic_range, brightness, tonal |

Alembic note: `sqlalchemy.url` in `alembic.ini` is intentionally blank — overridden at runtime via `env.py`. Do not add a value there.

## Import Format Detection (`import_music.py`)

- **Bandcamp**: flat zip + `Artist - Album.zip` filename. Strips `Artist - Album - ` prefix from track names. `cover.jpg` → `Folder.jpg`.
- **Amazon**: two-level subdirectory structure (`Artist/Album/track.mp3`). Decodes `__` → `/` in directory and file names. Copies any image file found at the album level.
- **Qobuz**: one-level subdirectory `Artist - Album/NN Title.flac`. FLACs transcoded to MP3 V0 (~245kbps) via ffmpeg subprocess. No cover art in Qobuz zips. ffmpeg is installed in the API Docker image.
- If no pattern matches, returns an error describing all three expected formats.

## Similarity Query

`GET /tracks/{id}/similar` is brute-force numpy (not pgvector ANN): fetches all vectors, z-score normalizes, applies per-user `sim_weight_*` scaling via `DIM_SLICES` (weights/5.0 multiplier), L2-normalizes, dot-product. Fast enough at ~3k tracks. HNSW index exists for future use.

`DIM_SLICES` in `tracks.py` maps 9 named groups to slice objects covering all 60 dimensions:
- `timbre` (0–12), `timbral_variation` (13–25), `harmony` (26–37), `chord_movement` (38–49)
- `tempo` (50), `loudness` (51), `dynamic_range` (52), `brightness` (53), `tonal` (54–59)

## Genre Tagging

`GET /albums/{id}/genres/fetch` and `GET /artists/{id}/genres/fetch` call Last.fm. `LASTFM_API_KEY` is read from `.env` via `config.py`. If the key is empty or Last.fm returns no match, these endpoints return `[]` — no error. Add `LASTFM_API_KEY=your_key` to `api/.env` to enable.

Genre writes (`POST /albums/{id}/genres`) normalize to lowercase before upsert. Both authenticated users (not owner-only) can tag — deliberate, see PRD.

`GET /albums/{id}/genres/suggest` reuses the same z-score + L2-normalize pipeline as `/tracks/{id}/similar` but lives in `albums.py`, not `tracks.py`. It has its own copy of `DIM_SLICES` (same values).

## Search

Uses `func.unaccent()` on both query and name/title columns — accent-insensitive search (e.g. "royksopp" finds "Röyksopp"). Requires `unaccent` PostgreSQL extension (already enabled via `CREATE EXTENSION IF NOT EXISTS unaccent`).
