# PRD: Vector Tuning (Ideal Vectors)

## Goal

Investigate and fix a perceived **quality regression** in the similarity engine:
the original 38-dim vector produced subjectively good results, and quality
appears to have *dropped* after expanding to 60 dims and adding the 9 sliders.
The aim is to determine whether the vector has too many / poorly-balanced
dimensions, and to land on a better-calibrated feature space and default
weighting — measured, not guessed.

This is the sibling of the **Music Map** PRD (`prd/music-map.md`); the Phase-1
map atlas is the primary visual instrument for this investigation.

## Leading Hypothesis: structural group-size imbalance

Reading `api/app/routers/tracks.py` (`similar_tracks`) and
`indexer/app/index.py` (`extract_features`) reveals a concrete, likely cause.

The pipeline is: store raw vectors → z-score per dimension (unit variance) →
multiply each group by `sim_weight/5.0` → L2-normalize the 60-vector →
cosine via dot product. After z-scoring, **every dimension contributes equally**
to the cosine. But the 9 groups have very unequal dimension counts:

| Group | Dims | Count | Share at neutral |
|---|---|---|---|
| timbre | 0–12 | 13 | 21.7% |
| timbral_variation | 13–25 | 13 | 21.7% |
| harmony | 26–37 | 12 | 20.0% |
| chord_movement | 38–49 | 12 | 20.0% |
| tonal | 54–59 | 6 | 10.0% |
| tempo | 50 | 1 | 1.7% |
| loudness | 51 | 1 | 1.7% |
| dynamic_range | 52 | 1 | 1.7% |
| brightness | 53 | 1 | 1.7% |

**Consequences:**

1. At neutral (all sliders = 5), **timbre drives the cosine ~13× more than
   tempo** purely because it has 13 dimensions to tempo's 1. The single-dim
   perceptual features (tempo, loudness, dynamic range, brightness) are nearly
   invisible.
2. The 38→60 expansion *shifted the balance the wrong way*: it added 12 more
   harmony-adjacent dims (chroma variance) + 6 tonnetz, further diluting the
   single-dim features and over-weighting harmonic/timbral texture. A richer
   vector that *feels worse* is exactly what an imbalance like this produces.
3. The sliders cannot fully compensate: even tempo at max (10 → 2× multiplier)
   only reaches ~3% of the vector. A single-dim group can never compete with a
   13-dim block under L2-normalized cosine.

### Candidate fix (to validate, not assume): per-group balancing

Scale each group so that **each group contributes equally at neutral**,
independent of its dimension count — e.g. divide each group's dimensions by
`sqrt(group_dim_count)` (so the group's vector-norm contribution is normalized),
*then* apply the `sim_weight/5.0` multiplier. Under this scheme:

- Neutral weights = every musical *concept* weighted equally (tempo == timbre),
  which matches user intuition far better than "timbre counts 13×."
- Sliders become genuinely expressive end-to-end — pushing tempo to 10 now has
  real effect because tempo started at parity.

This is one lever; the investigation must confirm it helps before shipping, and
weigh it against simply pruning dimensions.

## Diagnostics to Build/Run

A throwaway-friendly analysis (script in `indexer/` or a notebook against the DB)
plus the visual map. Produce a short written findings report.

1. **PCA explained variance** on the z-scored 60-D vectors. If ~90% of variance
   lives in the first ~10 components, most dimensions are redundant → confirms
   "too many dims." Report the scree curve and cumulative variance.
2. **Inter-group correlation** — correlation matrix across the 9 groups (and
   within the big blocks). High correlation between chroma-mean and chroma-var,
   or chroma and tonnetz, would justify pruning. Tonnetz (6 dims) vs chroma-mean
   (12 dims) overlap is a prime suspect.
3. **Group-contribution audit** — quantify each group's actual share of the
   cosine at neutral weights (confirm the table above empirically on real data,
   since z-scored variance is unit but realized contribution depends on
   correlation structure).
4. **A/B retrieval comparison** — for a handful of seed tracks the owner knows
   well, compare top-N neighbors under: (a) current 60-dim neutral, (b) 38-dim
   subset (original groups only), (c) per-group-balanced 60-dim. Subjective
   ranking by the owner is the ground truth here — there is no labeled dataset.
5. **Map inspection** — view the Phase-1 atlas colored by cluster and by single
   feature. A single undifferentiated blob vs. clean islands is direct visual
   evidence; scanning the single-feature lens shows which axes actually organize
   the space.

## Levers (decide based on diagnostics)

In rough order of likely impact:

- **A. Per-group balancing** (the candidate fix above) — likely highest impact,
  low risk, no re-index required (it's a query-side weighting change in
  `tracks.py` + the duplicate in `albums.py` genre-suggest, and in the map's
  weighted-cluster endpoint). Mirror in `DIM_SLICES` handling.
- **B. Prune redundant dimensions** — drop groups/dims the correlation + PCA
  analysis show as redundant (candidate: chroma variance and/or part of tonnetz).
  Requires a migration to change `vector(60)` → `vector(N)` + truncate + full
  re-index (same shape as migration 0010), plus updating `DIM_SLICES`,
  `extract_features`, the indexer model dimension, and the slider UI. Higher cost
  — only if balancing alone doesn't recover quality.
- **C. Recalibrate default weights** — if some groups are perceptually less
  important, ship non-uniform defaults instead of all-5. Cheap (column defaults +
  per-existing-user update), but balancing (A) is the more principled version of
  this.
- **D. Normalization review** — confirm z-score is the right scaler; consider
  robust scaling (median/IQR) if outlier tracks (very long/quiet) skew means.

## Sequencing

Per the Music Map PRD, the clean order resolving the chicken-and-egg (the map is
the tool to judge the vectors, but the vectors are what the map embeds):

1. **Music Map Phase 1** (minimal atlas) — gives the visual diagnostic.
2. **This PRD** — run diagnostics, choose levers, implement & validate.
3. **Music Map Phase 2** — polished map consuming the cleaned-up vectors.

## Validation

- No labeled ground truth exists — the owner's subjective A/B judgment on known
  seed tracks is the acceptance signal.
- Lock in a change only if it improves the owner's blind-ish ranking on the seed
  set *and* the map shows cleaner/more interpretable cluster separation.
- Whatever ships, update: `api/CLAUDE.md` and `indexer/CLAUDE.md` similarity
  notes, `DIM_SLICES` (both copies — `tracks.py` and `albums.py`), the slider UI
  if groups change, and `prd/vector-expansion.md` / `prd/similarity-weights.md`
  cross-references.

## Out of Scope

- Learned/ML embeddings (training a model on play history) — far future.
- External metadata enrichment (MusicBrainz/AcousticBrainz) — deferred per the
  global project constraints.
- Re-architecting the brute-force numpy query into pgvector ANN — orthogonal
  performance work; fine at current scale.
```