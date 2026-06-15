# PRD: Radio Modes (Selectable Continuation Algorithms)

## Goal

Radio mode today is a **random walk**: when the queue empties, the track that just
finished becomes the seed for the next `GET /tracks/{id}/similar` lookup, and the
top result becomes the new seed in turn. With well-tuned Sound Matching weights this
feels great; with oddly-tuned weights it drifts — each hop is "similar to the last
song," so over a long session the station wanders arbitrarily far from where it
started, bouncing across genres and artists you wouldn't expect.

This PRD keeps that behavior (now named **Classic**) and adds **selectable radio
modes** that constrain drift in different ways, plus a **Radio Modes** settings page
— modeled on the existing **Sound Matching** modal — that lets the user pick the
active algorithm and read a plain-language description of each.

---

## Background: how continuation works today

- All radio logic lives client-side in `web/src/player/PlayerContext.jsx`
  (`_extendWithRadio`). It calls `GET /tracks/{lastPlayed}/similar?limit=25`, filters
  out session-played tracks and the seed's album, and appends the top candidate.
- `sessionPlayedRef` (a `Set`) holds every track played since the last manual
  `playTrack()` and is the only drift/repeat guard.
- `GET /tracks/{id}/similar` (`api/app/routers/tracks.py`) is brute-force numpy:
  z-score normalize → apply per-user `sim_weight_*` via `DIM_SLICES` → L2-normalize →
  cosine (dot product). It returns a **ranked list only** — no distances, and it can
  only rank against an existing **track id**, not an arbitrary query vector.

The new modes need two things the current endpoint can't provide: ranking against a
**computed query vector** (anchor midpoints, centroids) and **distance values**
(ripple radius). The client has no access to the raw vectors. So the math must move
behind a new server endpoint.

---

## The Modes

All distances/geometry happen in the **weighted, z-scored space** — i.e. apply the
user's `sim_weight_*` scaling to z-scored vectors, then operate there. "Distance" is
cosine distance (`1 − cosine_similarity`) on L2-normalized vectors, so it stays
consistent with what Sound Matching already controls. "Query vector" means: build the
target vector in that space, L2-normalize it, rank all candidates by cosine to it.

### 1. Classic (current behavior — default)

Seed = last played track. Rank by similarity, exclude session-played + seed album,
take the top candidate. Wanders freely. **Remains the default** so existing behavior
is unchanged for anyone who doesn't visit the new page.

### 2. Anchor

The track that *starts* the radio session is the **anchor** A. Each next query vector
is the midpoint between the anchor and the track that just finished:

```
Q_n = normalize( (A + last_played) / 2 )
```

Pick the nearest unplayed track to `Q_n` (excluding the anchor's album and the
session-played set).

**Why it resists drift:** the query point is always pinned halfway to the anchor, so
selections stay in the anchor's neighborhood. It self-expands gracefully — as the
local neighborhood gets used up, nearest-unplayed drifts slightly farther, nudging
the midpoint outward just enough to keep finding fresh material without ever cutting
the tether.

**Known limitation (mitigated):** the midpoint constrains distance *to the anchor*,
not distance *between consecutive songs* — two tracks at the same radius can sit on
opposite sides of A, producing the occasional jarring back-to-back transition. To
mitigate, candidates are additionally required to be within a cohesion cap of the
track that just played (reuse the same `last_played` distance the ripple mode
computes). Candidates failing the cohesion cap are dropped before the nearest-to-`Q_n`
pick; if the cap empties the list, it is relaxed rather than stopping radio.

### 3. Ripple (Concentric Rings — "journey outward")

Start radius `r = 0` at the seed S. Pick the nearest track, set `r` to its distance
from S. Each subsequent pick is the **nearest track whose distance from S is greater
than the current radius**, and `r` advances to that track's distance.

**Honest framing:** this is *not* a cohesion mode — a monotonically increasing radius
marches from most-similar to least-similar and eventually reaches the far side of the
library from S. It is a **discovery / journey** mode: starts right at home, ventures
progressively further. This is a feature, not a bug — from a large library it yields
hours of evolving radio off a single seed, and across many different seeds it gives a
lot of variety. It does self-terminate once `r` exceeds the library's spread (radio
stops silently, same as an empty candidate list), but at thousands of tracks that's a
multi-day horizon — mathematically real, practically irrelevant.

The real concern is **not** running out of music; it's the shell quirk below.

**Free benefit:** the monotone radius means you can never re-pick something closer
than what already played, so **no played-set storage is needed** to avoid backtracking
— the radius is the history. (We still keep a small recent-set to suppress exact
repeats at tie distances.)

**Quirk:** a "ring" is a shell; two tracks at the same radius can be far from each
other, so consecutive jumps can be large. Apply the same consecutive-cohesion cap as
Anchor to smooth transitions where possible.

### 4. Anchored Ripple (the synthesis — recommended for "stays cohesive")

Combines the two ideas the user proposed:

- **Anchor tether** keeps the query near A (cohesion).
- **Soft minimum radius** from the anchor grows slowly, so repeats/backtracking are
  prevented **without storing a long played list** (the ripple insight).
- **Consecutive-distance cap** keeps back-to-back tracks close (smooth transitions).

Selection rule for the next track:

```
candidates = tracks where
    dist(A, t) > r_soft          # don't fall back inward (no-backtrack, no history needed)
    AND dist(last_played, t) < cohesion_cap   # smooth transition
choose argmin dist(Q_n, t)       # Q_n = normalize((A + last_played)/2)
then r_soft = max(r_soft, small_step * dist(A, chosen))   # gentle outward creep
```

This gives bounded drift (anchor), monotone-ish anti-repeat (soft radius), and smooth
transitions (cohesion cap), with minimal ephemeral state.

### Optional refinement: cluster-aware start region (Phase 2)

**Problem it solves:** a seed sitting on the boundary between two neighborhoods makes
*every* similarity-driven mode oscillate across the seam — track 1 lands in cluster A,
track 2 is "similar" but in cluster B, track 3 back in A. Clustering lets radio
**commit to one neighborhood early** and only cross the boundary later, once that
neighborhood is well-explored ("after radio's been playing for a while").

**Approach — k-NN-graph community detection, computed in the user's weighted space at
radio-start:**

- *Not* DBSCAN (distance concentration in 60-dim flattens the density contrast it keys
  on; produces excess "noise" points; no natural centroids). *Not* HNSW-as-clusterer
  (HNSW is the ANN index, it partitions nothing — but its k-NN graph is the right
  substrate). *Not* TDA/Mapper (heavy dependency, no crisp track→cluster label;
  overkill for a ~3k-track personal library).
- Use **Louvain/Leiden community detection on the k-NN graph**. Robust in high
  dimension because it keys on *relative* neighbor structure, not absolute density.
  At ~3k nodes it runs in milliseconds.
- **Compute it once at radio-start, in the user's weighted z-scored space** — *not*
  precomputed/global. Clusters are weight-dependent: a single index-time clustering
  would ignore each user's Sound Matching weights and mismatch their perceived
  similarity. With exactly two users and ~3k tracks, the weighted matrix is already
  built per request, so running community detection once per radio session is bounded
  and stays consistent with Sound Matching.

**Where the computed boundaries live (state, not storage):** the clustering result —
a compact `track_id → community_id` label map (**one small integer per track**: ~3700
entries, ≈ 3.7 KB raw / single-digit KB gzipped, *not* the 60-dim vectors, which never
leave the server) plus the current fenced community — has to survive across a session's
`/radio/next` calls, or every track would re-cluster from scratch. It is **ephemeral session state, held
client-side**, exactly like `played_ids`/`radius`/`anchor_id`: computed on the first
`/radio/next` of a session, returned to the client, echoed back on subsequent calls.
So there is **no new database/schema storage and no index-time precompute** — but it
*is* state, not free. (Alternatives considered: a server-side per-session cache —
genuine server state, fragile across workers, departs from the stateless `/radio/next`
design; or stateless recompute every call — wasteful, and Louvain's non-determinism
would make the fence *flicker* mid-session unless seeded. Compute-once-and-hold both
avoids the recompute cost and pins the boundaries so they don't wobble while playing.)

**How it layers onto the modes (most valuable for Ripple / Anchored Ripple):**

- Identify the seed's community = the **start cluster**.
- **Fence, don't relocate:** keep the seed itself as the played track, but pull the
  anchor toward the cluster core. The user pressed play on a specific song — don't
  teleport the musical center to the centroid.
- Constrain candidates to the start cluster while it still has unplayed material
  (Ripple's radius grows but stays fenced to the community). Once exhausted, **drop the
  fence and ripple into the adjacent community** — "explore this neighborhood
  thoroughly, then move next door" instead of bouncing across the seam from track one.
- Expose as a **Cluster stickiness** toggle/slider on the Radio Modes page (off = today's
  behavior; higher = stays in-cluster longer before breaching).

**Weights reshape the clusters (by design).** The communities are derived from the
k-NN graph *in the user's weighted space*, so the weights are effectively the distance
metric — changing a Sound Matching slider anisotropically stretches the space and
therefore changes which tracks are neighbors and which communities exist. Clustering
per-session in the weighted space (not a global index-time precompute) is exactly what
keeps the fence consistent with the weights in effect when the session started. Since
the label map is ephemeral, a weight change costs nothing — the next session just
re-clusters.

*Mid-session* weight changes re-draw the fences. **Decided:** moving a Sound Matching
slider re-clusters, so the neighborhoods always reflect the weights currently in
effect — the intuitive behavior for a user who doesn't know how this is plumbed.

Mechanism (server-self-detecting, no client awareness of weights needed): when the
server computes the label map it **stamps it with a fingerprint of the weights it was
built under** (e.g. a hash of the nine `sim_weight_*` values) and returns that stamp
alongside the labels. The client treats the stamp as opaque and just echoes it back on
the next `/radio/next`. On each call the server compares the stamp's weights-hash to
the user's *current* weights; if they differ (slider moved), it discards the passed-in
labels, re-clusters once in the new weighted space, and returns a fresh label map +
new stamp. So a weight change anywhere — even with a station already playing — makes
the very next track use freshly drawn fences, with no version-bumping plumbing on the
client.

Cost note: this is the "perhaps computationally expensive" part, but it's **one-time
per session start, plus one re-cluster each time the weights change** — never
per-track. Defer to Phase 2; v1 ships the four modes + Variety without it.

### 5. Top-K sampling (modifier, not a standalone mode)

Every mode above picks the single nearest candidate, which can feel repetitive. Add a
per-user **Variety** setting (0 = always pick #1, higher = sample from the top-K by
similarity, weighted toward the top). Orthogonal to mode choice; layers onto whichever
mode is active. Ship as a single slider on the Radio Modes page.

---

## Backend

### New endpoint: `POST /radio/next`

Auth required. One mode-agnostic call that keeps all vector math + per-user weights
server-side. Request body (ephemeral state owned by the client):

```jsonc
{
  "mode": "classic" | "anchor" | "ripple" | "anchored_ripple",
  "anchor_id": 1234,          // track that started the session (null for classic)
  "last_id": 1240,            // most recently finished track (classic seed)
  "played_ids": [1234, 1240], // session history to exclude (omit/short for ripple modes)
  "radius": 0.18,             // ripple state; null on first call
  "source_album_id": 88,      // album playing when radio kicked in — excluded
  "variety": 0                // 0–10; top-K sampling temperature
}
```

Response (or `204 No Content` when no candidate remains → radio stops, like today):

```jsonc
{
  "track": { /* enriched: id, title, track_number, duration_ms, bitrate_kbps,
                format, play_count, album_id, album_title, artist_id, artist_name */ },
  "radius": 0.21              // updated ripple state to echo back next call
}
```

- Reuses the existing pipeline in `tracks.py` (z-score → `sim_weight_*` via
  `DIM_SLICES` → L2-normalize). Factor that pipeline into a shared helper so
  `/tracks/{id}/similar`, `/albums/{id}/genres/suggest`, and `/radio/next` stop
  duplicating it (there are currently two copies of `DIM_SLICES`).
- Builds the query vector per mode (track lookup, midpoint, or centroid), ranks the
  full matrix, applies the mode's distance/exclusion rules, and returns one enriched
  track + updated radius. Track enrichment matches `/tracks/{id}/similar` so
  `playTrack()` field requirements are met.
- Returns `404` if `anchor_id`/`last_id` has no vector yet (not indexed), mirroring
  `/tracks/{id}/similar`.

### Persisting the chosen mode: migration 0013

For parity with Sound Matching (server-side, per user, syncs to Android) add to
`users`:

```
radio_mode    VARCHAR(16) NOT NULL DEFAULT 'classic'
radio_variety INTEGER     NOT NULL DEFAULT 0   -- 0–10 top-K temperature
```

Extend `PUT /auth/similarity-weights` (or add a sibling `PUT /auth/radio-settings`)
to accept partial updates of these, validated against the mode enum and 0–10 range.
`GET /auth/me` returns both fields. **The on/off radio toggle stays in `localStorage`
exactly as it is today** — only the algorithm choice and variety move server-side.

---

## Web

### Radio Modes page (modeled on `SimilarityWeightsModal.jsx`)

New `RadioModesModal.jsx`, opened from the user menu entry **"Radio Modes"** (next to
"Sound Matching"). Layout mirrors the Sound Matching modal:

- A radio-group list of the four modes. Each row: mode name + one-sentence plain
  description (the "what it does / when to use it" copy — no math jargon). Selected
  mode highlighted in accent, same styling vocabulary as `sim-weight-*`.
- A single **Variety** slider (0–10) beneath the list, with the existing
  `sim-weight-slider` styling.
- Reset-to-defaults / Cancel / Save actions like Sound Matching.
- Save → `PUT /auth/radio-settings`, invalidate `['me']`.

Suggested user-facing copy:

| Mode | Description |
|---|---|
| **Classic** | Follows the trail — each song picks the next most similar one. Adventurous; can roam across genres. |
| **Anchor** | Keeps circling back to the song you started with, so the station stays in one neighborhood. |
| **Ripple** | A journey outward — starts right at home and gradually ventures into less similar music. |
| **Anchored Ripple** | Stays close to your starting song while always finding something new. The most cohesive option. |
| *Variety slider* | Higher = more surprises; lower = always the closest match. |

### PlayerContext changes

- Read `radio_mode` + `radio_variety` from `['me']`; fall back to `'classic'` / `0`.
- Track an **anchor** alongside the existing `sessionPlayedRef`: set `anchorRef` to the
  track that was playing when radio first extends the queue (i.e. the seed of the first
  `_extendWithRadio` after a manual `playTrack`). Reset on every manual `playTrack`
  (same lifecycle as `sessionPlayedRef`).
- Maintain `radiusRef` for ripple modes; reset with the anchor.
- Replace the `GET /tracks/{id}/similar` call in `_extendWithRadio` with
  `POST /radio/next`, passing mode + anchor_id + last_id + played_ids + radius +
  source_album_id + variety. On `204`/empty, stop (current behavior). Echo `radius`
  back into `radiusRef`.
- `skipNext` at end-of-queue already routes through `_extendWithRadio` — unchanged.

---

## Android

Out of scope for v1 of this PRD beyond the data model. The shared
`RadioQueueExtender` (used by `MusicService` + `PlayerViewModel`, see the Android Auto
work) should later call `POST /radio/next` instead of `/tracks/{id}/similar`, and the
Settings sheet should gain a "Radio Modes" entry beside "Sound Matching". Because the
mode lives on the user row and `/radio/next` is mode-agnostic, Android picks up the
behavior with only the endpoint swap + a settings UI — no algorithm logic on-device.

---

## Implementation Plan

### Backend
1. `api/alembic/versions/0013_add_radio_settings.py` — `radio_mode VARCHAR(16)
   DEFAULT 'classic'`, `radio_variety INTEGER DEFAULT 0` on `users`.
2. `api/app/models.py` — add the two columns to `User`.
3. Factor the z-score → weights → L2 pipeline into a shared helper (e.g.
   `app/similarity.py`); update `/tracks/{id}/similar` and `/albums/{id}/genres/suggest`
   to use it (kills the duplicate `DIM_SLICES`).
4. `api/app/routers/radio.py` — `POST /radio/next` implementing all four modes +
   top-K sampling; register router in the app.
5. `api/app/routers/auth.py` — `PUT /auth/radio-settings` (partial, validated);
   include `radio_mode`/`radio_variety` in `GET /auth/me`.

### Frontend
6. `web/src/components/RadioModesModal.jsx` — mode radio-group + Variety slider.
7. `web/src/components/Layout.jsx` — "Radio Modes" entry in the user menu.
8. `web/src/player/PlayerContext.jsx` — anchor/radius refs; swap `_extendWithRadio`
   to `POST /radio/next`; read mode/variety from `['me']`.

---

## Open Decisions

- **Default mode:** **decided — Classic** (zero behavior change; the new modes are
  opt-in via the Radio Modes page).
- **Cohesion cap / soft-radius step constants:** need tuning against the real ~3k-track
  library; start with cap = 75th-percentile of nearest-neighbor distances, step = small.
  The cohesion cap is the load-bearing knob — it's what prevents the same-radius /
  opposite-sides-of-the-shell jumps that are Ripple's real failure mode.
- **Mode choice scope:** per-user (this PRD) vs. per-session ephemeral like the on/off
  toggle. Per-user chosen for Sound Matching parity + Android sync.

---

## Out of Scope

- Saved "radio station" snapshots — queue stays ephemeral.
- *Genre*-based hard-fencing (genre tags are too sparse). Note: *similarity-cluster*
  fencing is in scope but deferred to Phase 2 — see "Optional refinement" above. It
  adds a community-detection dependency (e.g. `python-louvain`/`igraph`/`leidenalg`)
  to the API image; v1 ships without it.
- Neural embeddings — still deferred per the original radio PRD.
- Android UI (data model only here; endpoint swap tracked under Android Auto).
- Changing Sound Matching weights themselves — radio modes consume the same weighted
  space, they don't alter it.
