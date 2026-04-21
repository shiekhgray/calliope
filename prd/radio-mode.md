# PRD: Radio Mode (Continuous Playback via Similarity)

## Goal

When the queue runs out, Calliope keeps playing — automatically selecting the most
similar track to whatever just finished. Feels like a radio station tuned to your
taste, not a shuffle. Default-on; user can disable it per session with a toggle in
the player bar.

---

## User-Facing Behavior

### Radio toggle

A radio/antenna icon button lives in `PlayerBar` to the right of the existing
controls. State: **on** (accent color) or **off** (muted).

- Default: **on**
- Persisted in `localStorage` so the preference survives page reloads
- When off: playback stops normally at the end of the queue
- When on: as soon as the last track in the queue ends, Calliope picks the next one

### Queue extension

When radio mode fires:

1. Take the track that just finished as the seed
2. Query for the N most similar tracks in the library (N = 25, enough to avoid
   repetition without over-fetching)
3. Filter the candidate list:
   - Exclude tracks already played in the current session (queue history)
   - Exclude tracks that belong to the same album or playlist the user was
     listening to when radio kicked in ("source context")
4. Pick the top remaining candidate and append it to the queue
5. Repeat each time the queue empties

Radio extends one track at a time, on demand — no pre-queuing. This keeps the
seed always current (the most recently played track).

### Session reset

The played-tracks set and source context are reset when the user manually starts
a new context — clicking a track, starting an album, or starting a playlist. Radio
mode state (on/off) is not reset.

### Empty result

If the filter leaves zero candidates (unlikely at 3000 tracks, but possible in a
very small library or after extended listening), radio mode silently stops — same
behavior as radio-off. No error shown.

---

## Similarity Index

### Storage: pgvector

Feature vectors are stored in Postgres using the `pgvector` extension. Two tables:

```
track_vectors       track_id (FK → tracks.id, unique), feature_vector (vector(38)), file_mtime (bigint)
vector_norm_params  id (always 1), means (float[38]), stds (float[38]), updated_at
```

`file_mtime` (Unix timestamp, integer seconds) is used for incremental indexing —
if the stored mtime matches the file on disk, the track is skipped during rescan.

**Raw vectors are stored unnormalized.** Normalization is applied at query time using
the parameters in `vector_norm_params`. This means adding new tracks never requires
touching existing vector rows — only the norm params are recomputed after each rescan.

A cosine similarity index (`ivfflat` or `hnsw`) on `feature_vector` allows fast
nearest-neighbor queries. At 3000 tracks brute-force is also fine; the index is
forward-looking.

### Feature vector: 38 dimensions

As specified in `music_similarity_design.md`:
- 26-dimensional MFCC vector (13 mean + 13 variance across frames)
- 12-dimensional chroma vector (pitch class histogram)

### Normalization

Raw vectors are z-score normalized at query time: `(v - means) / stds` applied
per dimension. This puts all 38 dimensions on equal footing so no single feature
(e.g. MFCC coefficient 0, which tracks overall loudness) dominates similarity.

After each rescan's indexing phase, norm params are recomputed from the full
`track_vectors` table — a mean/std over a ~3000×38 matrix, which takes
milliseconds. No existing vector rows are modified.

### Alembic migration

New migration enables `pgvector`, creates `track_vectors` table, and adds the
cosine similarity index.

---

## Incremental Indexing (Rescan Integration)

The existing `POST /scanner/trigger` background task gains a second phase:

**Phase 1 (existing)**: walk the library, upsert artist/album/track metadata in Postgres.

**Phase 2 (new)**: for each track now in the DB, check if `track_vectors` has a row
with a matching `file_mtime`. If yes: skip. If no (new file or file changed): extract
features and upsert the vector.

This means a normal rescan on an unchanged library adds zero re-indexing overhead.
A rescan after adding 20 new albums only processes those 20 albums.

Feature extraction uses `librosa` (audio loading, MFCC, chroma) and `numpy` (vector
math, normalization). These are added to `api/requirements.txt`. `librosa` is heavy
(pulls in scipy/scikit-learn); it is imported lazily inside the indexing phase so
API startup time is unaffected.

### Scanner status

The existing `/scanner/status` response gains two optional fields:
```json
{
  "running": true,
  "phase": "indexing",          // "scanning" | "indexing" | null
  "indexed": 12,
  "to_index": 47
}
```

The web UI rescan progress indicator shows these fields if present. Existing behavior
(no phase/counts) unchanged for backwards compatibility.

---

## API

### `GET /tracks/{id}/similar?limit=25`

Auth required. Returns up to `limit` tracks sorted by cosine similarity DESC.
Response shape matches `GET /albums/{id}` track entries (includes `album_id`,
`album_title`, `artist_id`, `artist_name`) so `playTrack()` enrichment requirements
are met.

Returns 404 if the track has no vector yet (not yet indexed).

---

## Implementation Plan

### Backend
1. `api/alembic/versions/0006_add_pgvector.py` — enable extension, create
   `track_vectors` table, add cosine index
2. `api/app/models.py` — `TrackVector` model
3. `api/scripts/scan.py` — Phase 2: incremental feature extraction + upsert into
   `track_vectors`; normalization computed over all vectors after batch insert
4. `api/app/routers/tracks.py` — `GET /tracks/{id}/similar`
5. `api/requirements.txt` — add `librosa`, `pgvector`

### Frontend
6. `PlayerContext.jsx`:
   - Add `radioMode` state (default true, persisted to localStorage)
   - Add `toggleRadioMode()`
   - Add `sessionPlayed` set (track IDs played since last manual context start)
   - Add `sourceContext` (album_id or playlist_id that was playing when radio first kicked in)
   - In `onended`: if queue empty and radioMode on, call `GET /tracks/{last}/similar`,
     filter, pick top result, call `playTrack()`
7. `PlayerBar.jsx` — radio toggle button (icon, accent when on)

---

## Out of Scope

- Saved "radio playlists" — queue is ephemeral, nothing is persisted
- Genre or mood scoping for radio (full library is the pool)
- BPM/tempo matching (not captured by MFCC+chroma; deferred per design doc)
- Neural embeddings (CLAP/OpenL3) — deferred, worth revisiting if quality is poor
- Radio seeded from a playlist (playlist context triggers radio when the playlist ends,
  but the seed is still the last track played, not a playlist aggregate)
- Android radio support (Phase 5)
