# Indexer — Calliope Similarity Engine

Separate Docker container (`python:3.12-slim`). Runs on port 8001. Does NOT serve the web — it processes audio files and writes feature vectors to the shared PostgreSQL database.

## HTTP API

```
POST /index       — start indexing; 202 Accepted, 409 if already running
GET  /status      — {"running": bool, "indexed": int, "to_index": int}
POST /map/rebuild — full UMAP re-fit of the Music Map atlas; 202, 409 if busy
```

Plain Python stdlib `http.server` — no FastAPI, no external HTTP framework. Thread-safety via a module-level `_lock` + `_running` bool.

The API scanner router (`api/app/routers/scanner.py`) calls this after scan.py completes (phase 2 of the two-phase rescan).

## Feature Vector: 60 Dimensions

| Dims | Feature | Librosa call |
|---|---|---|
| 0–12 | MFCC mean | `mfcc.mean(axis=1)` |
| 13–25 | MFCC variance | `mfcc.var(axis=1)` |
| 26–37 | Chroma mean | `chroma_stft.mean(axis=1)` |
| 38–49 | Chroma variance | `chroma_stft.var(axis=1)` |
| 50 | Tempo | `librosa.beat.beat_track()` → `np.atleast_1d(tempo)[0]` |
| 51 | RMS mean | `rms.mean()` |
| 52 | RMS variance | `rms.var()` |
| 53 | Spectral centroid mean | `spectral_centroid.mean()` |
| 54–59 | Tonnetz mean | `librosa.feature.tonnetz(y=librosa.effects.harmonic(y))` |

Analysis window: first 60s of each file at 22050 Hz mono. `librosa.effects.harmonic(y)` applied before tonnetz to improve accuracy on percussive tracks.

Expanded from 38→60 dims via migration 0010 (breaking: track_vectors truncated, full re-index required).

## Database Tables

```
track_vectors      track_id (PK FK→tracks), feature_vector vector(60), file_mtime bigint
vector_norm_params id (always 1), means float[60], stds float[60], updated_at
track_map_coords   track_id (PK FK→tracks), x REAL, y REAL, cluster_id int, updated_at  (Music Map; written by mapping.py)
```

HNSW cosine index on `track_vectors(feature_vector)` — created in migration 0006. Currently unused at query time (API does brute-force numpy); forward-looking for when the library grows.

## Incremental Indexing

`run_indexing()` in `index.py`:
1. Fetches all tracks with their stored `file_mtime` (LEFT JOIN — null = not yet indexed)
2. Checks actual mtime on disk; skips files where stored mtime matches
3. Extracts features for stale/new files, upserts `TrackVector` row
4. After batch: recomputes `VectorNormParams` from all rows (z-score means/stds)

Vectors are stored **raw** (unnormalized). Normalization is applied at query time in the API.

## Music Map Atlas (`mapping.py`)

`build_map(db, full_refit)` projects the 60-dim vectors to fixed 2-D coordinates and stores them in `track_map_coords` (migration 0013). Called automatically at the end of `run_indexing()` with `full_refit=False`; the manual `POST /map/rebuild` runs it with `full_refit=True`.

- Preprocessing mirrors the similarity engine: z-score via `vector_norm_params` (neutral weights) → L2-normalize → UMAP `metric="euclidean"` (L2-norm makes euclidean ≈ the cosine the engine uses).
- **Full refit:** `UMAP(n_neighbors=15, min_dist=0.1, n_components=2).fit_transform(...)`, pickle the model to `MAP_MODEL_PATH` (default `/data/umap_model.pkl`, backed by the `indexer_data` docker volume).
- **Incremental:** `reducer.transform()` only tracks missing from `track_map_coords` — frozen geography, cheap. Existing points keep their coords; only `cluster_id` is refreshed.
- Default `cluster_id`: compact deterministic k-means++ (`kmeans()`, 16 clusters) on the full 60-D z-scored+L2 space. Mirrored by the API's `_kmeans` in `map.py` so neutral-weight colors line up (note: k-means label identity is sensitive to track-count drift between a full refit and a later live recompute — call-to-call determinism for a fixed input is what's guaranteed).
- **Query via the `TrackVector` ORM model, not raw `text()` SQL** — pgvector deserializes the vector column to a list only through the ORM; raw SQL returns it as a string (same gotcha as `_recompute_norm_params`).
- **`umap-learn 0.5.6` requires `scikit-learn < 1.7`** (it calls `check_array(force_all_finite=)`, removed in sklearn 1.7). `scikit-learn==1.5.2` is pinned in `requirements.txt` for this reason.

## Normalization (Query Side, in API)

`GET /tracks/{id}/similar` in `api/app/routers/tracks.py`:
1. Fetches `VectorNormParams` (means, stds)
2. Fetches all `TrackVector` rows
3. Normalizes: `(v - means) / stds` per dimension
4. L2-normalizes each normalized vector
5. Dot-product against the query track's normalized vector
6. Returns top-N by cosine similarity (brute-force numpy, not pgvector ANN)

Returns 404 if the query track has no vector yet.

## Gotchas

- **`indexer/app/models.py` must match the DB column dimension.** After migration 0010 changed `track_vectors.feature_vector` to `vector(60)`, the indexer model still declared `Vector(38)`. The pgvector Python client validates client-side before inserting, so every insert failed silently. Fix: update `models.py`, rebuild the indexer container. If you expand dimensions again, update both the migration AND `indexer/app/models.py`.
- `librosa` is a heavy import (scipy/scikit-learn). It is imported inside `index.py` only — never at API startup. Keep it this way.
- MFCC coefficient 0 tracks overall loudness and would dominate cosine similarity without normalization. Normalization is non-negotiable.
- WAV files sometimes have unreliable sample rates. Loading at `sr=22050` (fixed resample) avoids issues.
- `np.atleast_1d(tempo)[0]` needed for tempo extraction — librosa 0.10.x returns either a scalar or a 1-element array depending on the input.

## Docker

```dockerfile
FROM python:3.12-slim
RUN apt-get install -y libsndfile1 ffmpeg gcc
```

- `libsndfile1` required by librosa for WAV/FLAC decoding
- `ffmpeg` required for MP3/M4A decoding via soundfile backend
- Music volume mounted read-only at `/music` (indexer only reads files)
- Shares the same PostgreSQL database as the API container

## Development

```bash
# Trigger indexing manually
curl -X POST http://localhost:8001/index

# Check status
curl http://localhost:8001/status | jq .

# Or via the web UI: user menu → Rescan Library (triggers both phases)
```
