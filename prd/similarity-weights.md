# PRD: Similarity Weights

## Goal

Let each user tune how the similarity engine weighs the three semantic groups
of the feature vector. Three sliders in the user menu (0–10 each, default 5)
control how much emphasis is placed on timbre, energy, and harmony when finding
similar tracks and in radio mode.

## Background

> **Note**: `prd/vector-expansion.md` expands the feature vector from 38 to
> 60 dimensions and adds 6 new slider groups. The canonical dimension map and
> full 9-slider UI spec live there. This PRD covers the weighting mechanism
> and user-facing UI; read both together.

The feature vector has semantic groups that map 1:1 to user-facing sliders.
After z-score normalization, each group's dimensions are multiplied by the
user's weight for that group before the final L2-normalization step. Since
only relative weights matter (cosine similarity is scale-invariant), equal
weights across all sliders is equivalent to the current unweighted engine.

**Current vector (38 dims, 3 sliders):**

| Dims | Feature | Musical meaning |
|------|---------|-----------------|
| 0–12 | MFCC mean | Timbral character — tone color, instrumentation |
| 13–25 | MFCC variance | How much the texture changes within the track |
| 26–37 | Chroma mean | Harmonic content — pitch class distribution, key |

**After vector expansion (60 dims, 9 sliders):** see `prd/vector-expansion.md`
for the full dimension map and updated slider layout.

## Database Changes

Three new columns on `users`:

```sql
sim_weight_timbre   INTEGER NOT NULL DEFAULT 5
sim_weight_dynamics INTEGER NOT NULL DEFAULT 5
sim_weight_harmony  INTEGER NOT NULL DEFAULT 5
```

Stored as integers 0–10. Applied directly as numpy scalars — no further
normalization needed (all three at equal values = neutral regardless of the
value).

Migration: `0008_add_similarity_weights.py` (or next available number at
implementation time).

## API Changes

### `GET /auth/me` — add weight fields

```json
{
  "id": 1,
  "username": "graham",
  "sim_weight_timbre": 5,
  "sim_weight_dynamics": 5,
  "sim_weight_harmony": 5
}
```

### `PUT /auth/similarity-weights` — new endpoint

Auth required. Validates all values are integers in [0, 10].

Request:
```json
{ "timbre": 8, "dynamics": 3, "harmony": 6 }
```

Response: updated `me` object (same shape as `GET /auth/me`).

### `GET /tracks/{id}/similar` — apply user weights

The endpoint already receives `current_user` for auth. Now reads
`current_user.sim_weight_timbre/dynamics/harmony` and applies them in the
numpy pipeline immediately after z-score normalization, before L2-normalization:

```python
weights = np.ones(38, dtype=np.float32)
weights[0:13]  *= current_user.sim_weight_timbre   / 5.0
weights[13:26] *= current_user.sim_weight_dynamics / 5.0
weights[26:38] *= current_user.sim_weight_harmony  / 5.0
matrix *= weights  # broadcast over rows
```

Dividing by 5.0 converts the stored 0–10 integer to a 0–2 multiplier relative
to the neutral baseline. The L2-normalization step that follows is unchanged.

Radio mode (`_extendWithRadio` in PlayerContext) calls this same endpoint and
inherits the weights automatically — no frontend changes needed.

## Web UI Changes

### User menu — new "Sound Matching" item

Added below "Change Password" and above "Rescan Library" in the dropdown.
Opens a modal (`SimilarityWeightsModal.jsx`).

### `SimilarityWeightsModal.jsx`

Reads initial values from the `['me']` React Query cache (already fetched by
`AuthContext`). Three labeled sliders:

```
Timbre
  Tone color and instrumentation character
  [━━━━━━━━●━━] 7

Energy
  How much the texture varies within the track
  [━━●━━━━━━━━] 3

Harmony
  Harmonic and pitch content
  [━━━━━●━━━━━] 5
```

- Range: 0–10, step 1, HTML `<input type="range">`
- Current value displayed to the right of each slider
- Slider track uses `--accent` for the filled portion (via `accent-color` CSS
  property or a custom range style consistent with the existing volume slider)
- **Save** button fires `PUT /auth/similarity-weights`; on success, invalidates
  both `['me']` and `['similar', currentTrackId]` React Query keys, then closes
  the modal — so the Now Playing similar tracks section refreshes automatically
  with the new weights without any navigation. `currentTrackId` comes from
  `usePlayer()` (already available in Layout where the modal is mounted).
- **Reset to defaults** link (small, muted) sets all three to 5 without saving,
  so the user can see the defaults before committing
- Saving is the only write — moving sliders is purely local state until Save

### No other frontend changes

Radio mode and the Now Playing similar-tracks section pick up the new weights
automatically because the weights are applied server-side.

## Out of Scope

- Per-playlist or per-session weight overrides (global user setting is enough)
- Exposing the raw dimension indices or vector values to the user
- Fractional slider steps (integer steps 0–10 give 11 positions, which is
  plenty of granularity for a perceptual tuning control)
- Explaining the math to the user in the UI — the subtitle lines are sufficient
