# PRD: Music Map

## Goal

A visual, interactive map of the entire music library — every track plotted as a
point in 2-D space, positioned so that musically similar tracks land near each
other. The map serves two purposes that share one canvas:

1. **Browse** — explore the library spatially, see neighborhoods/genres emerge,
   discover clusters, hover any point for artist/album/track + mini cover art.
2. **Tune** — while adjusting the Similarity Weights sliders, watch the
   neighborhood structure (via color) reflow in real time, and see where the
   currently-playing track's radio neighbors fall. This makes the otherwise
   invisible behavior of the similarity engine legible.

This is the headline consumer of the 60-dim feature vectors beyond radio/similar,
and a diagnostic instrument for the companion **Vector Tuning** PRD
(`prd/vector-tuning.md`).

## Core Design Decisions (settled during design)

These were worked out deliberately; the rationale matters because each one kills
a tempting-but-wrong alternative.

### Positions come from a layout algorithm, not from raw dimensions

You cannot "pick 2 or 3 of the 60 dimensions and graph them" — any 2 raw axes
discard ~58 dimensions of structure, so spatially-close points would not actually
be similar. Position must come from a **dimensionality-reduction algorithm** that
projects 60-D → 2-D while preserving neighborhood structure.

**Use UMAP.** It preserves local neighborhoods (clusters), which is exactly the
"map" metaphor. t-SNE is comparable but slower and less stable run-to-run; PCA is
fast/deterministic but smears clusters together (optimizes global variance, not
locality). UMAP primary, PCA as a trivial fallback if a UMAP fit ever fails.

### The geography is FIXED; only color is live

The map positions are computed **once, offline, per scan** — not recomputed when
the user drags a slider. This is the single most important decision and it
deletes the hardest engineering problem:

- A weighted re-layout on every slider drag means a fresh global UMAP fit each
  time (seconds). UMAP is a global optimization — it cannot stream or do
  "nearest-first," so progressive/seed-centric re-layout is not viable.
- Instead, **positions stay put** (your mental map never scrambles) and the
  **cluster coloring is recomputed live** under the current weights. Re-clustering
  ~3k points is sub-second; re-laying-out is not. See "Live re-coloring" below.
- Because positions never move on a weight change, **page load is just shipping
  stored coordinates** — instant. No streaming machinery needed.

### 2-D, not 3-D

2-D wins: hover-to-pick is trivial (3-D has occlusion/depth ambiguity and forces
constant rotation), it works on a phone, and it keeps WebGL point rendering
simple. The third dimension's only payoff is "looks cool," which loses to the
interaction cost. The lost dimensions are recovered via **color**, not depth.

### Color is the recovery channel — with an honest limit

Color encodes the detail the 2-D projection lost, via a **selectable lens**:

- **Cluster** (categorical hues) — the default. Makes neighborhood boundaries
  visible. Clusters are computed in **full 60-D space**, NOT on the 2-D
  positions — that is what lets color reveal structure the projection smeared
  (two clusters that UMAP placed adjacent show as different colors).
- **Single feature** (perceptually-uniform gradient) — pick one of the 9 groups
  (tempo, brightness, harmony, …) and scan the map one axis at a time. This is
  the diagnostic gold for the Vector Tuning PRD: you see which features actually
  organize the library vs. which are noise.
- **3-PC gestalt** (the "RGB idea") — map the top 3 principal components to a
  color space. Honest framing: a human cannot *decode* 3 color channels back into
  3 values, but "similar color ≈ similar region of feature space" reads well even
  when 2-D position lied. Use it as a whole-shape-at-a-glance overview, not a
  quantitative readout.

**Color spaces:** for the single-feature gradient, default to a
**perceptually-uniform** map (OKLab / CIELAB, or a prebuilt ramp like viridis).
Raw RGB and HSV both lie to the eye — equal data steps don't look equal. (This is
the same OKLab-interpolation issue already documented in the root CLAUDE.md
dynamic-accent note.) Offer HSV/RGB as toggles for the PC-gestalt mode, where the
goal is differentiation rather than magnitude. Never light up more than ~2
encodings at once (e.g. hue + size) before it turns to soup.

### Incremental maintenance

UMAP's full fit is all-at-once and global — but **adding points later is not**.
`umap.transform()` projects new tracks into the existing frozen embedding without
moving the old points:

- **First build:** full `.fit()` on the whole library; pickle the fitted model.
- **After a scan adds tracks:** `.transform()` only the new tracks into the
  frozen space. Cheap, and the existing geography stays stable.
- **Occasional full re-fit:** refresh quality after large growth (scheduled /
  manual). `transform()` placement is slightly lower quality than a from-scratch
  fit — a brand-new track in a genre with no neighbors yet can land awkwardly;
  the periodic re-fit cleans that up.

## Library Scale

Current library is ~3k tracks (per the brute-force similarity note in
`api/CLAUDE.md`). Design for headroom to ~20k. At 3k, even a canvas/SVG scatter
works; for smooth pan/zoom and headroom, render with a WebGL point library
(recommended: `regl-scatterplot`, which is purpose-built for pan/zoom/hover/select
on large point sets; deck.gl `ScatterplotLayer` is the heavier alternative).

## Data Model

New table, separate from `track_vectors` so the HNSW index and the vector column
are untouched:

```sql
CREATE TABLE track_map_coords (
    track_id    INTEGER PRIMARY KEY REFERENCES tracks(id) ON DELETE CASCADE,
    x           REAL NOT NULL,
    y           REAL NOT NULL,
    cluster_id  INTEGER,          -- default (neutral-weight) cluster
    updated_at  TIMESTAMP NOT NULL DEFAULT now()
);
```

Migration: next available number (0013+). The fitted UMAP model is pickled to a
persistent path so `.transform()` can run on later scans — store at e.g.
`/data/umap_model.pkl` inside the indexer container, backed by a named docker
volume (the indexer currently mounts music read-only and has no writable data
volume — add one).

**Preprocessing must mirror the similarity engine** so the map is a faithful
picture of what the engine sees: apply the same z-score normalization
(`vector_norm_params`) the API uses in `/tracks/{id}/similar`, with **neutral
weights** (no per-user scaling) for the fixed atlas. The atlas therefore honestly
reflects the current group-size imbalance documented in the Vector Tuning PRD —
that is a feature, not a bug; the map is partly how we'll *see* that imbalance.

## Indexer Changes (`indexer/`)

UMAP runs in the indexer container (it already owns the numpy-heavy, librosa-heavy
work and is the natural home for an offline batch step).

1. Add `umap-learn` to `indexer/requirements.txt` (pulls numba — heavy; acceptable
   in this container, which already carries librosa/scipy).
2. New module `indexer/app/mapping.py`:
   - `build_map(db, full_refit: bool)`:
     - Fetch all `track_vectors`, z-score with `vector_norm_params`.
     - If `full_refit` or no pickled model: `UMAP(n_neighbors=15,
       min_dist=0.1, n_components=2, metric="euclidean").fit_transform(...)`,
       pickle the model.
     - Else: `transform()` only tracks missing from `track_map_coords`.
     - Compute default clusters in full 60-D z-scored space (KMeans, `k`
       configurable ~12–20; HDBSCAN is a nicer-boundaries alternative but adds a
       dep and is slower — KMeans keeps offline and online clustering identical).
     - Upsert `track_map_coords` rows.
3. Call `build_map(full_refit=False)` at the end of `run_indexing()` (after
   `_recompute_norm_params`), so a normal rescan keeps the map current. Expose a
   manual full-refit trigger (HTTP `POST /map/rebuild` on the indexer's stdlib
   server, mirroring `/index`).

## API Changes (`api/`)

### `GET /map` — fetch all points (auth)

Returns one row per track with everything the canvas + hover tooltip need. ~3k
rows is small (<1 MB); no pagination for now.

```json
[
  {
    "track_id": 412, "x": 1.83, "y": -0.42, "cluster_id": 7,
    "artist_id": 33, "artist_name": "Test Artist",
    "album_id": 88, "album_title": "Test Album", "track_title": "Test Track"
  }
]
```

Cover art uses the existing `GET /albums/{id}/art` endpoint, loaded lazily on
hover (don't ship art with the point list).

### `GET /map/clusters?weighted=true` — live re-coloring (auth)

Recomputes cluster assignments under the **current user's** `sim_weight_*` values,
reusing the exact preprocessing from `/tracks/{id}/similar` (z-score → per-group
`w/5.0` scaling → L2-normalize), then KMeans. Returns `{track_id: cluster_id}`.

This is the slider-tuning payload: drag sliders → call this on release → recolor
the fixed points. KMeans on ~3k×60 is sub-second. Implement KMeans as a compact
numpy routine (≈15 lines) to avoid adding scikit-learn to the API image; seed
deterministically (k-means++ or fixed RNG) so colors are stable between calls
with unchanged weights. Cluster→hue assignment must be stabilized (e.g. sort
clusters by centroid position) so colors don't shuffle arbitrarily between calls.

### `GET /map/lens?feature=tempo` — single-feature gradient (auth)

Returns `{track_id: value}` where value is the track's z-scored value for the
chosen group (mean across the group's dims), min-max scaled to 0–1 for direct
colormap input. `feature` is one of the 9 `DIM_SLICES` keys. Cheap.

### Radio overlay

No new endpoint — reuse `GET /tracks/{id}/similar` for the currently-playing
track and highlight those IDs on the map (the weighted top-N neighborhood).

## Web Changes (`web/`)

- New route `/map` + nav entry.
- `MapPage.jsx`:
  - WebGL scatter (`regl-scatterplot`) of `GET /map` points; pan + zoom.
  - **Hover tooltip** — a positioned div showing artist / album / track title +
    a small lazily-loaded album-art thumbnail. (Your original instinct — correct
    and easy in 2-D.)
  - **Lens selector** — Cluster (default) / Single feature (dropdown of the 9
    groups) / 3-PC gestalt; plus a color-space toggle where applicable.
  - **Side panel with the Similarity Weights sliders** embedded (reuse the
    `SimilarityWeightsModal` slider components). On change → debounced
    `GET /map/clusters?weighted=true` → recolor in place. Save still persists via
    the existing `PUT /auth/similarity-weights`.
  - **Now-playing highlight** — the current track is emphasized (size/ring) and
    its `/similar` neighbors are lit up, so you watch the radio neighborhood shift
    as you tune.
  - **Click a point** → play that track (enrich with album_id/title/artist as the
    web player requires), or open its album.

## Phasing

**Phase 1 — Minimal atlas (also the Vector Tuning diagnostic).**
Indexer UMAP fit + `track_map_coords` + `GET /map` + WebGL scatter + hover
tooltip + default cluster color. Ship this first; it's the visual tool the Vector
Tuning PRD needs to judge the vectors.

**Phase 2 — Lenses + live tuning.**
`/map/lens`, `/map/clusters?weighted`, the lens selector, embedded sliders with
live recolor, color-space toggles, now-playing radio highlight, click-to-play.

## Open Questions / Decisions Deferred

- **Personalization of positions** — v1 positions are unweighted (only color
  personalizes). A per-user weighted *layout* would require a UMAP fit per user
  and re-scramble the geography on every weight change; explicitly out of scope.
  Revisit only if color+highlight prove insufficient.
- **Clustering algorithm** — KMeans chosen for speed/consistency; HDBSCAN
  (organic boundaries + noise points) is a possible later upgrade if the Vector
  Tuning work shows the library has non-spherical neighborhoods.
- **Android** — out of scope for v1; this is a web-first feature.

## Out of Scope

- 3-D rendering / three.js.
- Re-laying-out positions on slider change (color reflow only).
- Real-time UMAP (offline batch only).
- Shipping raw 60-D vectors to the client (all reduction/clustering server-side).
- Per-user persisted map layouts.
```