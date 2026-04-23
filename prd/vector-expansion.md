# PRD: Vector Expansion (60-Dim Feature Vector)

## Goal

Expand the similarity feature vector from 38 to 60 dimensions by adding six
new musically meaningful feature groups: chroma variance, tempo, RMS loudness,
RMS dynamic range, spectral brightness, and tonal character. This gives the
similarity engine and radio mode a much richer musical picture, and provides
the per-group sliders in the Similarity Weights feature with enough axes to be
genuinely expressive.

## New Feature Groups

| Dims  | Feature | Librosa call | Musical meaning |
|-------|---------|--------------|-----------------|
| 0–12  | MFCC mean | `mfcc.mean(axis=1)` | Tone color, instrumentation *(existing)* |
| 13–25 | MFCC variance | `mfcc.var(axis=1)` | How much timbre changes within the track *(existing)* |
| 26–37 | Chroma mean | `chroma.mean(axis=1)` | Average pitch-class / harmonic content *(existing)* |
| 38–49 | **Chroma variance** | `chroma.var(axis=1)` | How much harmony moves — low = static drone, high = rapid chord changes |
| 50    | **Tempo** | `beat_track(y, sr)[0]` | BPM — pace of the music |
| 51    | **RMS mean** | `rms(y).mean()` | Average loudness |
| 52    | **RMS variance** | `rms(y).var()` | Dynamic range — how much the loudness varies |
| 53    | **Spectral centroid mean** | `spectral_centroid(y, sr).mean()` | Brightness — high = treble-heavy, low = bass-heavy |
| 54–59 | **Tonal character** | `tonnetz(harmonic(y), sr).mean(axis=1)` | 6-dim tonal centroid — captures key, mode, and harmonic relationships more precisely than raw chroma |

**Total: 60 dimensions** (was 38, +22 new)

### Why these features

- **Chroma variance**: the natural companion to chroma mean, same as MFCC var
  is to MFCC mean. Distinguishes a droning static piece from a harmonically
  restless one even when their average pitch content is similar.
- **Tempo**: the most glaring gap in the current vector. Two tracks can share
  identical MFCC and chroma profiles and be a completely different musical
  experience at 70 BPM vs 140 BPM.
- **RMS mean + variance**: captures overall loudness level and dynamic range
  independently. A compressed pop mix and a wide-dynamic orchestral recording
  may sound similar spectrally but feel very different.
- **Spectral centroid**: brightness proxy. Bass-heavy dub vs shimmery
  post-rock may share chroma and tempo characteristics but live in opposite
  ends of the frequency spectrum.
- **Tonnetz**: librosa's 6-dimensional tonal centroid (fifths, minor thirds,
  major thirds axes). More musically sophisticated than chroma mean for
  detecting key relationships and mode — captures major vs minor character
  that raw pitch-class histograms miss.

## Breaking Change

Changing `feature_vector` from `vector(38)` to `vector(60)` invalidates all
existing rows and the HNSW index. The migration must:

1. Drop the HNSW cosine index on `track_vectors`
2. Truncate `track_vectors` (all rows invalid — wrong dimension)
3. Delete the `vector_norm_params` row (means/stds arrays are now the wrong length)
4. Alter the column type to `vector(60)`
5. Recreate the HNSW index for `vector(60)`

After migration, the next indexer run re-indexes everything from scratch.
The mtime check naturally handles this: truncating `track_vectors` means all
tracks have `stored_mtime = NULL` and are queued for re-indexing.

```sql
DROP INDEX IF EXISTS track_vectors_hnsw_idx;
TRUNCATE track_vectors;
DELETE FROM vector_norm_params;
ALTER TABLE track_vectors ALTER COLUMN feature_vector TYPE vector(60)
    USING NULL;  -- column is empty after TRUNCATE, USING clause is a no-op
CREATE INDEX track_vectors_hnsw_idx
    ON track_vectors USING hnsw (feature_vector vector_cosine_ops);
```

Migration file: `0008_vector_expansion.py` (or next available number).

## Code Changes

### `indexer/app/index.py` — `extract_features()`

```python
def extract_features(file_path: Path) -> np.ndarray:
    """Return a 60-dim feature vector.

    Dims  0–12: MFCC mean
    Dims 13–25: MFCC variance
    Dims 26–37: chroma mean
    Dims 38–49: chroma variance
    Dim  50:    tempo (BPM)
    Dim  51:    RMS mean
    Dim  52:    RMS variance
    Dim  53:    spectral centroid mean
    Dims 54–59: tonnetz mean
    """
    y, sr = librosa.load(str(file_path), sr=22050, mono=True, duration=ANALYSIS_DURATION)

    mfcc   = librosa.feature.mfcc(y=y, sr=sr, n_mfcc=13)
    mfcc_mean = np.mean(mfcc, axis=1)       # 13
    mfcc_var  = np.var(mfcc, axis=1)        # 13

    chroma = librosa.feature.chroma_stft(y=y, sr=sr)
    chroma_mean = np.mean(chroma, axis=1)   # 12
    chroma_var  = np.var(chroma, axis=1)    # 12

    tempo, _ = librosa.beat.beat_track(y=y, sr=sr)
    tempo_val = float(np.atleast_1d(tempo)[0])   # 1

    rms = librosa.feature.rms(y=y)[0]
    rms_mean = np.mean(rms)                 # 1
    rms_var  = np.var(rms)                  # 1

    centroid = librosa.feature.spectral_centroid(y=y, sr=sr)[0]
    centroid_mean = np.mean(centroid)       # 1

    y_harm = librosa.effects.harmonic(y)
    tonnetz = librosa.feature.tonnetz(y=y_harm, sr=sr)
    tonnetz_mean = np.mean(tonnetz, axis=1) # 6

    return np.concatenate([
        mfcc_mean, mfcc_var,
        chroma_mean, chroma_var,
        [tempo_val], [rms_mean], [rms_var], [centroid_mean],
        tonnetz_mean,
    ]).astype(np.float32)
```

`np.atleast_1d(tempo)[0]` handles librosa returning either a scalar or a
one-element array depending on version (0.10.x can return either).

`librosa.effects.harmonic(y)` uses a median filter to separate the harmonic
component before computing tonnetz — improves accuracy for tracks with heavy
percussion. Fast enough that it doesn't meaningfully increase indexing time.

### `api/app/routers/tracks.py` — similarity weight application

The dimension slice constants need updating once vector expansion ships.
If similarity weights ships first at 38 dims, these slices must be updated
in the same release as the vector expansion migration:

```python
DIM_SLICES = {
    "timbre":           slice(0, 13),
    "timbral_variation": slice(13, 26),
    "harmony":          slice(26, 38),
    "chord_movement":   slice(38, 50),
    "tempo":            slice(50, 51),
    "loudness":         slice(51, 52),
    "dynamic_range":    slice(52, 53),
    "brightness":       slice(53, 54),
    "tonal":            slice(54, 60),
}
```

## Impact on Similarity Weights PRD

The similarity weights PRD (`prd/similarity-weights.md`) was written for
the 38-dim vector with 3 sliders. This expansion changes it to **9 sliders**
across **9 weight columns** on `users`. The existing 3 columns stay; 6 are added:

| Column | Dims | Default | Slider label |
|--------|------|---------|--------------|
| `sim_weight_timbre` | 0–12 | 5 | Tone Color |
| `sim_weight_timbral_variation` | 13–25 | 5 | Timbral Variation |
| `sim_weight_harmony` | 26–37 | 5 | Harmonic Content |
| `sim_weight_chord_movement` *(new)* | 38–49 | 5 | Chord Movement |
| `sim_weight_tempo` *(new)* | 50 | 5 | Tempo |
| `sim_weight_loudness` *(new)* | 51 | 5 | Loudness |
| `sim_weight_dynamic_range` *(new)* | 52 | 5 | Dynamic Range |
| `sim_weight_brightness` *(new)* | 53 | 5 | Brightness |
| `sim_weight_tonal` *(new)* | 54–59 | 5 | Tonal Character |

**Rename note**: the existing `sim_weight_dynamics` column should be renamed
to `sim_weight_timbral_variation` when this ships — "Dynamics" is now a
better fit for the RMS-based loudness/dynamic-range sliders.

### Slider UI layout (updated `SimilarityWeightsModal.jsx`)

Sliders grouped visually into three sections:

```
── Timbre ──────────────────────────────
Tone Color          How the instruments sound          [slider]
Timbral Variation   How much the texture changes       [slider]
Brightness          Bass-heavy vs treble-heavy         [slider]

── Harmony ─────────────────────────────
Harmonic Content    What notes/chords are present      [slider]
Chord Movement      How fast the harmony changes       [slider]
Tonal Character     Key, mode, and chord relationships [slider]

── Rhythm & Energy ─────────────────────
Tempo               Pace of the music (BPM)            [slider]
Loudness            Average volume level               [slider]
Dynamic Range       How much the volume varies         [slider]
```

## Dependency Note

These two features are tightly coupled. The recommended implementation order:

1. **Vector expansion first** — migration + re-index + update dimension slices
2. **Similarity weights second** — build the 9-slider UI against the 60-dim vector

If similarity weights ships first (3-slider version for 38-dim vector), the
vector expansion migration must update the `users` table in the same pass to
add the 6 new weight columns and rename `sim_weight_dynamics`.

## Out of Scope

- Spectral contrast, zero crossing rate, or other additional features — the
  9 groups above are comprehensive enough for this use case
- Per-feature normalization tuning — z-score norm params handle scale
  differences automatically (BPM and Hz values will be normalized just like
  the MFCC values are)
- Incremental migration (re-using old 38-dim vectors) — not feasible; the
  vector shape must be uniform across all rows for pgvector to function
- Onset strength or tempogram — meaningful but redundant given tempo + MFCC var
