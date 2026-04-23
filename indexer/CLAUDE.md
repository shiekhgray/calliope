# Indexer — Calliope Similarity Engine

Separate Docker container (`python:3.12-slim`). Runs on port 8001. Does NOT serve the web — it processes audio files and writes feature vectors to the shared PostgreSQL database.

## HTTP API

```
POST /index   — start indexing; 202 Accepted, 409 if already running
GET  /status  — {"running": bool, "indexed": int, "to_index": int}
```

Plain Python stdlib `http.server` — no FastAPI, no external HTTP framework. Thread-safety via a module-level `_lock` + `_running` bool.

The API scanner router (`api/app/routers/scanner.py`) calls this after scan.py completes (phase 2 of the two-phase rescan).

## Feature Vector: 38 Dimensions

| Dims | Feature | Librosa call |
|---|---|---|
| 0–12 | MFCC mean | `mfcc.mean(axis=1)` |
| 13–25 | MFCC variance | `mfcc.var(axis=1)` |
| 26–37 | Chroma mean | `chroma_stft.mean(axis=1)` |

Analysis window: first 60s of each file at 22050 Hz mono. Fast enough in practice (~hundreds of tracks per minute).

**Vector expansion planned** (`prd/vector-expansion.md`): 38→60 dims, adding chroma variance, tempo, RMS, spectral centroid, tonnetz. Breaking migration — requires truncating track_vectors and full re-index.

## Database Tables

```
track_vectors      track_id (PK FK→tracks), feature_vector vector(38), file_mtime bigint
vector_norm_params id (always 1), means float[38], stds float[38], updated_at
```

HNSW cosine index on `track_vectors(feature_vector)` — created in migration 0006. Currently unused at query time (API does brute-force numpy); forward-looking for when the library grows.

## Incremental Indexing

`run_indexing()` in `index.py`:
1. Fetches all tracks with their stored `file_mtime` (LEFT JOIN — null = not yet indexed)
2. Checks actual mtime on disk; skips files where stored mtime matches
3. Extracts features for stale/new files, upserts `TrackVector` row
4. After batch: recomputes `VectorNormParams` from all rows (z-score means/stds)

Vectors are stored **raw** (unnormalized). Normalization is applied at query time in the API.

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
