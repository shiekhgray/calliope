"""Build the key-invariant similarity space (track_vectors_ki) from track_vectors.

Key-invariance is a pure rotation of already-extracted chroma — no audio, no
librosa. For each track: detect the tonic from the stored chroma_mean via
Krumhansl-Schmuckler, then roll the chroma_mean (dims 26-37) and chroma_var
(dims 38-49) blocks so the tonic sits at index 0. Timbre/perceptual/tonnetz dims
are copied unchanged. Then recompute z-score norm params over the rotated matrix
and store them as vector_norm_params id=2.

Idempotent: rebuilds the whole table from scratch each run. Safe to re-run after
any rescan to resync. Run inside the api container:

    docker compose exec api python scripts/build_ki_vectors.py
"""
import sys
from datetime import datetime

import numpy as np

# Allow running as `python scripts/build_ki_vectors.py` from /app.
sys.path.insert(0, "/app")

from app.database import SessionLocal
from app import models

KI_NORM_ID = 2

# Krumhansl-Kessler major/minor key profiles (12 pitch-class weights each).
KK_MAJ = np.array([6.35, 2.23, 3.48, 2.33, 4.38, 4.09, 2.52, 5.19, 2.39, 3.66, 2.29, 2.88])
KK_MIN = np.array([6.33, 2.68, 3.52, 5.38, 2.60, 3.53, 2.54, 4.75, 3.98, 2.69, 3.34, 3.17])


def detect_tonic(chroma_mean: np.ndarray) -> int:
    """Tonic pitch-class (0-11) maximizing correlation over all 24 keys."""
    c = chroma_mean - chroma_mean.mean()
    cn = np.linalg.norm(c)
    if cn == 0:
        return 0
    best_corr, best_root = -2.0, 0
    for prof in (KK_MAJ, KK_MIN):
        p = prof - prof.mean()
        pn = np.linalg.norm(p)
        for r in range(12):
            corr = float(np.dot(c, np.roll(p, r))) / (cn * pn)
            if corr > best_corr:
                best_corr, best_root = corr, r
    return best_root


def key_invariant(vec: np.ndarray) -> np.ndarray:
    """Rotate the chroma blocks of a 60-dim vector to its detected tonic."""
    out = vec.copy()
    shift = detect_tonic(vec[26:38])
    out[26:38] = np.roll(vec[26:38], -shift)   # chroma_mean (harmony)
    out[38:50] = np.roll(vec[38:50], -shift)   # chroma_var  (chord_movement)
    return out


def main():
    db = SessionLocal()
    try:
        rows = db.query(models.TrackVector).all()
        if not rows:
            print("track_vectors is empty — nothing to build.")
            return

        ki_rows = []
        matrix = np.empty((len(rows), 60), dtype=np.float64)
        for i, tv in enumerate(rows):
            v = np.array(tv.feature_vector, dtype=np.float64)
            kv = key_invariant(v)
            matrix[i] = kv
            ki_rows.append({
                "track_id": tv.track_id,
                "feature_vector": kv.tolist(),
                "file_mtime": tv.file_mtime,
            })

        # Rebuild the table from scratch (idempotent).
        db.query(models.TrackVectorKI).delete()
        db.bulk_insert_mappings(models.TrackVectorKI, ki_rows)

        # Z-score params over the rotated matrix (chroma dims now differ).
        means = matrix.mean(axis=0).tolist()
        stds = matrix.std(axis=0).tolist()
        norm = db.get(models.VectorNormParams, KI_NORM_ID)
        if norm is None:
            norm = models.VectorNormParams(id=KI_NORM_ID, means=means, stds=stds)
            db.add(norm)
        else:
            norm.means = means
            norm.stds = stds
            norm.updated_at = datetime.utcnow()

        db.commit()
        print(f"Built track_vectors_ki: {len(ki_rows)} rows; "
              f"norm params stored as vector_norm_params id={KI_NORM_ID}.")
    finally:
        db.close()


if __name__ == "__main__":
    main()
