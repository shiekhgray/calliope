# API — Calliope Backend

FastAPI app in `api/app/`. Code is baked into the Docker image — rebuild required after any Python change:
```
docker compose build api && docker compose up -d api
docker compose exec api alembic upgrade head
```

## Routers (`api/app/routers/`)

| File | Endpoints |
|---|---|
| `auth.py` | POST /auth/login (OAuth2 form), /auth/refresh, GET /auth/me (incl. radio_mode/radio_variety), POST /auth/change-password, PUT /auth/similarity-weights (partial, 0–10 per field), PUT /auth/radio-settings (partial; radio_mode enum + radio_variety 0–10) |
| `artists.py` | GET /artists (excludes VA), /artists/{id}/albums (album_type='album' only), /artists/{id}/singles (album_type IN ('single','ep'), includes first_track), /artists/{id}/top-tracks?limit=N (default 25, uses album_artists join), /artists/{id}/compilations, /artists/{id}/genres/fetch (Last.fm artist.getTopTags) |
| `albums.py` | GET /albums/{id} (includes album_type), /albums/{id}/art, PUT /albums/{id}/art (multipart, writes Folder.jpg), PATCH /albums/{id}/type (owner-only, validates album/ep/single); GET /albums/{id}/genres, GET /albums/{id}/genres/fetch (Last.fm), GET /albums/{id}/genres/suggest (similarity k-NN), POST /albums/{id}/genres (auth, both users), DELETE /albums/{id}/genres/{genre_id} (auth, both users) |
| `tracks.py` | GET /tracks?sort=play_count&limit=N (auth, default 50), GET /tracks/{id}/stream (byte-range, 512KB chunks), POST /tracks/{id}/played, GET /tracks/{id}/similar (per-user weighting via shared app/similarity.py) |
| `radio.py` | POST /radio/next (auth) — mode-agnostic continuation: classic/anchor/ripple/anchored_ripple + top-K Variety sampling. Stateless: client passes mode/anchor_id/last_id/played_ids/radius/source_album_id/variety, gets back one enriched track + updated radius (204 when no candidate). All geometry in the user's weighted z-scored space via app/similarity.py. |
| `genres.py` | GET /genres (accepts `?q=` for autocomplete filter, limit 20 when q set) |
| `search.py` | GET /search?q= (unaccent), GET/POST /search/history (auth; upsert + prune to 10) |
| `playlists.py` | Full CRUD + add/remove/reorder tracks + similar; all endpoints require auth; GET /playlists and GET /playlists/{id} gate by can_view; track mutations gate by can_edit; DELETE is owner-only; GET /playlists returns enriched card data: art_tracks (0–4, centroid-based 2-pass selection), preview_tracks (first 3 titles), top_genres (top 4 by frequency), track_count |
| `users.py` | GET /users (auth required) — returns [{id, username}] for all users |
| `map.py` | GET /map (all atlas points + hover metadata + default cluster), GET /map/clusters?weighted=&w= (live KMeans recolor under saved or `w=`-overridden weights; {track_id: cluster_id}), GET /map/lens?feature= (z-scored group mean, 0–1), GET /map/pca (top-3 PCs → per-track [r,g,b] 0–1). All auth. Music Map feature. |
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

- **`.album_type` marker**: an album dir may contain a hidden `.album_type` file (value `album`/`ep`/`single`) dropped by importers — e.g. `scripts/qobuz_import.py --loose` writes `single`. The scanner applies it **only when first creating the album**, so a later manual change via PATCH `/albums/{id}/type` is never clobbered on rescan. Empty suffix → never treated as a track or cover.

## Migrations

Applied: **0001–0015**. Next number: **0016**.

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
| 0012_add_playlist_permissions | `view_mode VARCHAR(10) DEFAULT 'everyone'`, `edit_mode VARCHAR(10) DEFAULT 'owner'` on `playlists`; new tables `playlist_viewers (playlist_id, user_id)`, `playlist_editors (playlist_id, user_id)` with cascade-delete FKs |
| 0013_add_track_map_coords | `track_map_coords (track_id PK→tracks cascade, x REAL, y REAL, cluster_id INT, updated_at)` — Music Map atlas; positions written by the indexer's UMAP step |
| 0014_add_radio_settings | `radio_mode VARCHAR(16) NOT NULL DEFAULT 'classic'`, `radio_variety INTEGER NOT NULL DEFAULT 0` on `users` (Radio Modes) |
| 0015_add_track_vectors_ki | `track_vectors_ki` (mirror of `track_vectors`, `vector(60)` + HNSW) — key-invariant similarity space (Vector Tuning experiment). Empty table only; populated by `scripts/build_ki_vectors.py`. KI z-score stats = `vector_norm_params` row id=2. |

Alembic note: `sqlalchemy.url` in `alembic.ini` is intentionally blank — overridden at runtime via `env.py`. Do not add a value there.

## Import Format Detection (`import_music.py`)

- **Bandcamp**: flat zip + `Artist - Album.zip` filename. Strips `Artist - Album - ` prefix from track names. `cover.jpg` → `Folder.jpg`.
- **Amazon**: two-level subdirectory structure (`Artist/Album/track.mp3`). Decodes `__` → `/` in directory and file names. Copies any image file found at the album level.
- **Qobuz**: one-level subdirectory `Artist - Album/NN Title.flac`. FLACs transcoded to MP3 V0 (~245kbps) via ffmpeg subprocess. No cover art in Qobuz zips. ffmpeg is installed in the API Docker image. Loose singles (bare `.flac`) via host-side `scripts/qobuz_import.py --loose` — tag-based placement, transcode, and drops a `.album_type=single` marker (see scanner notes).
- If no pattern matches, returns an error describing all three expected formats.

## Similarity Query

`GET /tracks/{id}/similar` is brute-force numpy (not pgvector ANN): fetches all vectors, z-score normalizes, applies per-user `sim_weight_*` scaling via `DIM_SLICES` (weights/5.0 multiplier), L2-normalizes, dot-product. Fast enough at ~3k tracks. HNSW index exists for future use.

**Shared helper:** `app/similarity.py` owns the canonical `DIM_SLICES` + the
z-score→weights→L2 pipeline (`load_weighted_matrix`) and track enrichment
(`enrich_tracks`). Both `/tracks/{id}/similar` and `/radio/next` import from it.

**Similarity spaces (`space` param):** three spaces, selected per request.
- **`embed` (DEFAULT)** — pretrained PANNs CNN14 audio embedding (`track_vectors_embed`,
  2048-dim). `load_embedding_matrix()` — plain L2-normalized cosine, **no z-score, no
  per-user weights** (a learned embedding has no weight-groups). Won the Vector Tuning
  owner A/B decisively (captures genre/instrumentation/vocals; see prd/vector-tuning.md).
  Default for both `GET /tracks/{id}/similar` and `/radio/next`.
- **`standard`** / **`ki`** — the 60-dim DSP spaces via `load_weighted_matrix(..., space=)`
  / `SPACES` map (`track_vectors` norm id=1 / `track_vectors_ki` norm id=2). Now
  **dev-only**, reachable via `?space=standard|ki`. The 9 `sim_weight_*` sliders (which
  only affect these) were retired from the web user menu; the columns + `PUT
  /auth/similarity-weights` remain (still used by the DSP-based Music Map tuning panel).

Embeddings are produced by the indexer (`app/embeddings.py`, PANNs), populated
incrementally at the end of each index run; full manual rebuild:
`docker compose exec indexer python -m app.embeddings`. The KI table is a regenerable
numpy derivative of `track_vectors` (chroma rotated to the Krumhansl-Schmuckler tonic):
`docker compose exec api python scripts/build_ki_vectors.py`.

**Radio note:** `/radio/next` geometry (cohesion caps, soft-radius step 0.5) was tuned
for the DSP cosine spread; embed cosines sit in a compressed ~0.88–0.99 band, so the
ripple/anchored modes need retuning for embed — classic/nearest works fine. Follow-up.
`albums.py` (genre suggest, no weights) and `map.py` (float64 + KMeans + `w=`
override) still carry their own specialized copies — keep all in sync if dims change.

`DIM_SLICES` maps 9 named groups to slice objects covering all 60 dimensions:
- `timbre` (0–12), `timbral_variation` (13–25), `harmony` (26–37), `chord_movement` (38–49)
- `tempo` (50), `loudness` (51), `dynamic_range` (52), `brightness` (53), `tonal` (54–59)

## Genre Tagging

`GET /albums/{id}/genres/fetch` and `GET /artists/{id}/genres/fetch` call Last.fm. `LASTFM_API_KEY` is read from `.env` via `config.py`. If the key is empty or Last.fm returns no match, these endpoints return `[]` — no error. Add `LASTFM_API_KEY=your_key` to `api/.env` to enable.

Genre writes (`POST /albums/{id}/genres`) normalize to lowercase before upsert. Both authenticated users (not owner-only) can tag — deliberate, see PRD.

`GET /albums/{id}/genres/suggest` reuses the same z-score + L2-normalize pipeline as `/tracks/{id}/similar` but lives in `albums.py`, not `tracks.py`. It has its own copy of `DIM_SLICES` (same values).

The Music Map endpoints in `map.py` also carry their own copy of `DIM_SLICES` (same values) and reuse the identical z-score → per-group `w/5.0` scaling → L2-normalize preprocessing. `/map/clusters` and the indexer's offline default clustering share a compact deterministic k-means++ (`_kmeans`, 16 clusters, centroid-sorted ids for stable hues) so neutral-weight colors line up between offline and online. The canonical `DIM_SLICES` now lives in `app/similarity.py` (used by tracks + radio); `albums`, `playlists`, and `map` still keep their own specialized copies — keep them in sync if dims ever change.

## Search

Uses `func.unaccent()` on both query and name/title columns — accent-insensitive search (e.g. "royksopp" finds "Röyksopp"). Requires `unaccent` PostgreSQL extension (already enabled via `CREATE EXTENSION IF NOT EXISTS unaccent`).
