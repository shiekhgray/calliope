# PRD: Rebase the Music Map onto the PANNs embedding

**Status: Not started — follow-up to Vector Tuning**

## Motivation

The Music Map (`prd/music-map.md`) projects the **60-dim DSP vector** to 2-D. As of
the Vector Tuning work (2026-06-18), similarity/radio now run on a **pretrained PANNs
CNN14 audio embedding** (`track_vectors_embed`, the default `space=embed`), and the
DSP spaces are dev-only. So the map currently visualizes a feature space the product
no longer uses — it should reflect the embedding that actually drives similarity.

Rebasing also retires the last consumer of the 9 `sim_weight_*` columns: the map's
"Tune weights" panel is the only remaining surface that reads/writes them (the user-menu
"Sound Matching" modal was already removed).

## Scope — three tiers

### Tier 1 — Minimal rebase (project the embedding)
- `indexer/app/mapping.py` `build_map()`: source `track_vectors_embed` instead of
  `track_vectors`; L2-normalize the 2048-dim embeddings → UMAP → `track_map_coords`.
  **PCA-reduce to ~50 dims before UMAP** (speed/stability on 2048-dim; standard practice).
  Pickled-model + incremental `transform()` flow unchanged. `run_indexing` already embeds
  before building the map, so ordering is fine. Requires one `POST /map/rebuild` (full refit).
- KMeans `cluster_id`: same, computed on the embedding (PCA-reduced) space.
- `api/app/routers/map.py`: rewrite preprocessing to use the embedding (drop z-score +
  `DIM_SLICES`; L2 only). **Remove the `?weighted&w=` variant of `/map/clusters`** (no
  weight-groups). `/map/pca` (3-PC gestalt) still works.
- `web/src/pages/MapPage.jsx`: remove the "Tune weights" panel + its `PUT
  /auth/similarity-weights` save path; remove the single-feature lens (see Tier 3) or
  leave a stub. Keep pan/zoom/hover-art/click-to-play/now-playing highlight, Clusters lens,
  3-PC gestalt lens.

### Tier 2 — Cleanup payoff (retire sim_weight_*)
Once nothing reads the weights:
- Migration: drop the 9 `sim_weight_*` columns from `users`.
- Remove `PUT /auth/similarity-weights` and the `radio_*`-adjacent weight plumbing in
  `app/similarity.py` `user_weight_vector` / `SPACES` weighting (the DSP `standard`/`ki`
  dev spaces would then run unweighted — acceptable since they're dev-only; or keep
  `load_weighted_matrix` weight logic behind a default-5 and just drop the per-user columns).
  Decide: fully remove DSP weighting, or keep neutral-only.
- `vector_norm_params` id=1/id=2 stay (still used by the DSP dev spaces).

### Tier 3 — Semantic lenses (recommended enhancement)
PANNs CNN14 also emits **527 AudioSet tag probabilities** per track (instruments, genres,
vocals) — currently discarded; it's the same inference pass, so capturing it is ~free.
- Extractor (`indexer/app/embeddings.py`): also persist `clipwise_output` (e.g. a
  `track_audio_tags` table, or top-K tags per track to keep it small).
- `/map/lens`: repoint from DSP-group means to **tag activations** — "color by *electric
  guitar* / *singing* / *synthesizer* / *drum kit* / *distorted guitar*." Strictly better
  than the old per-DSP-group lens and directly serves the owner's instrumentation interest
  (visually separate the distorted-guitar region from the synth region).
- `MapPage.jsx`: lens selector offers a searchable list of AudioSet tags instead of the 9
  DSP groups.

## Decisions / open questions
- **PCA-before-UMAP dim** (~50) — confirm fit time/quality on the ~3,900-point library.
- **Tier 2 reach**: drop sim_weight_* columns only, vs. also stripping all DSP weighting
  code. Leaning: drop the columns + `/auth/similarity-weights`; leave DSP spaces neutral.
- **Tag storage** (Tier 3): full 527-vector vs top-K per track. Top-K (e.g. 20) keeps it
  lean and the lens only needs presence/strength of a chosen tag.

## Out of scope
- Re-tuning radio for embed (separate Vector Tuning follow-up).
- Changing the default similarity space (already embed).

## Cross-refs
`prd/music-map.md`, `prd/vector-tuning.md`, `indexer/CLAUDE.md` (mapping.py),
`api/CLAUDE.md` (map.py), `web/CLAUDE.md` (MapPage). The map "doubles as the Vector
Tuning diagnostic" — post-rebase its role shifts to exploring the embedding space.
