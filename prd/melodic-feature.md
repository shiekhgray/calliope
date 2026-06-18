# PRD: Melodic Feature (stub)

**Status: Not started — exploratory stub**

## Motivation

The current 60-dim similarity vector captures **timbre** (MFCC) and **harmony**
(chroma / tonnetz) but has **no representation of melody** — no pitch contour, no
intervallic structure. This is a feature-*coverage* gap, distinct from the
weighting/key-invariance calibration work in `vector-tuning.md`.

It surfaced concretely in the Vector Tuning A/B: Lucius reharmonize and
re-instrument their songs heavily (live and across releases), so a demo and an
album cut of the same composition diverge in timbre *and* harmony — the only thing
held constant is the **melody**, which our vectors cannot see. Any artist whose
identity lives in melody (with deliberately variable arrangement) is invisible to
the current feature set.

## Goal

Add a melodic representation so the engine can recognize that two recordings share
a melody even when timbre/harmony differ — i.e. move from purely **content-based**
similarity ("what does it sound like now") toward optional **identity-aware**
similarity ("is this the same musical line"). Complements, does not replace, the
existing vector.

## Owner A/B finding (2026-06-17) — vocals are the primary similarity axis

A detailed owner listening pass (11 seeds, standard vs key-invariant; raw notes
were in `reactions.md`) showed that **vocal character dominates the owner's sense
of similarity**, and it is exactly what the current MFCC-over-the-whole-mix vector
cannot isolate. The discriminating attributes, in the owner's words:

- **Vocal presence** — instrumentals matching vocal-led tracks is the single worst
  failure ("no vocal!" / "no vocals, terrible match"; e.g. Armin van Buuren and
  general fuzz mismatched against Daft Punk / Morgan Page).
- **Rhythmic/syllabic vs. melodic/complex vocals** — Daft Punk's "robotic voice
  speaking syllabic words" matches Party Nails / Kamino / Yelle, but NOT the
  melodically complex Purity Ring or Arcade High "DGYK" ("should not match"),
  while Arcade High "Slay" (same syllabic style) *should* match and is missing.
- **Ethereal vs. confident/autotuned** — Men I Trust's ethereal soprano matches
  Goldmyth; confident uptempo pop (Katy Perry, Charli xcx) leaks in wrongly.
- **Soprano / vocal complexity + tempo** — Universal Hall Pass's "complex soprano"
  matches Delerium / L'Impératrice; Kill Hannah's "simple vocals + distorted
  guitars" should not.

**Implication:** the leakage from *very* dissimilar tracks (and the missed
should-match tracks) is a **missing-dimension** problem, not a weighting/key-frame
miscalibration. This feature should therefore prioritize the **vocal line**, not
generic predominant melody:

- **Vocal presence / salience** — is there a lead vocal, and how prominent?
- **Vocal melodic character** — rhythmic-syllabic vs. sustained-melodic,
  complexity, register (e.g. soprano), expressiveness.

Vocal-source isolation (e.g. a stem-separation step like Demucs/Spleeter before
melody/contour extraction) is likely required and is the main cost driver.

## Approaches to explore (not yet chosen)

- **Vocal stem isolation first** (Demucs / Spleeter) → derive features from the
  separated vocal: presence/energy, pitch-contour stats, register, note-rate
  (syllabic vs. sustained). Directly targets the owner's primary axis above.
- **Predominant-melody extraction** → pitch contour features (e.g. `librosa.pyin`,
  CREPE, or a Melodia-style salience approach). Aggregate to contour statistics.
- **Interval histogram** — distribution of melodic intervals; **key-invariant by
  construction** (intervals are relative), which dovetails with the key-invariant
  chroma space.
- **Melodic n-gram / contour shape descriptors** — direction/shape sequences,
  robust to transposition and tempo.
- **Self-similarity / fingerprint-ish** hybrids for true cover/version detection
  (harder; possibly a separate concern from radio similarity).

## Scope & cost

- New extraction in the indexer's `extract_features` + re-index of the full
  library (melody extraction is comparatively expensive and noisy).
- Likely new dimensions → migration (new `vector(N)` or a parallel melodic vector
  table, mirroring the `track_vectors_ki` parallel-table pattern).
- Validation: same owner-judged seed-track A/B as Vector Tuning; specifically test
  reharmonized/live/demo pairs (Lucius) and covers.

## Relationship to other work

- Sibling of `vector-tuning.md` (calibration) and the **key-invariant chroma
  space** (`track_vectors_ki`) work — melody is the next axis after harmony is made
  key-invariant.
- Out of scope until the key-invariant space A/B concludes.

## Out of scope

- Replacing the existing timbre/harmony vector — melody is additive.
- Full audio-fingerprint cover detection as a product feature (research only).
