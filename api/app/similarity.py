"""Shared similarity preprocessing.

The same pipeline — z-score normalize → apply per-user ``sim_weight_*`` scaling
→ L2-normalize — is used by ``/tracks/{id}/similar`` and ``/radio/next``. Keep it
in one place so the weighting math (and the ``DIM_SLICES`` group map) stays
consistent across endpoints. ``albums.py`` (genre suggest, no weights) and
``map.py`` (float64 + KMeans + ``w=`` override) carry their own specialized
copies on purpose.
"""
import numpy as np
from sqlalchemy import text
from sqlalchemy.orm import Session

from app import models

VECTOR_DIM = 60

# Maps the 9 named weight groups to their slice of the 60-dim feature vector.
DIM_SLICES = {
    "timbre":            slice(0, 13),
    "timbral_variation": slice(13, 26),
    "harmony":           slice(26, 38),
    "chord_movement":    slice(38, 50),
    "tempo":             slice(50, 51),
    "loudness":          slice(51, 52),
    "dynamic_range":     slice(52, 53),
    "brightness":        slice(53, 54),
    "tonal":             slice(54, 60),
}

_ENRICH_SQL = text("""
    SELECT t.id, t.title, t.track_number, t.duration_ms, t.bitrate_kbps,
           t.format, t.play_count, t.album_id,
           al.title AS album_title, ar.id AS artist_id, ar.name AS artist_name
    FROM tracks t
    JOIN albums al ON al.id = t.album_id
    JOIN artists ar ON ar.id = al.artist_id
    WHERE t.id = ANY(:ids)
""")


def user_weight_vector(user: models.User, dtype=np.float32) -> np.ndarray:
    """Per-dimension weight vector from the user's ``sim_weight_*`` columns."""
    weights = np.ones(VECTOR_DIM, dtype=dtype)
    for group, sl in DIM_SLICES.items():
        w = float(getattr(user, f"sim_weight_{group}", 5))
        weights[sl] *= w / 5.0
    return weights


def load_weighted_matrix(db: Session, user: models.User, dtype=np.float32):
    """Return ``(ids, matrix)`` for all indexed tracks in the user's weighted,
    L2-normalized space, or ``(None, None)`` if fewer than 2 vectors exist.

    ``ids`` is an int ndarray aligned row-wise with ``matrix`` (shape (N, 60)).
    Cosine similarity between rows is then a plain dot product.
    """
    all_tv = db.query(models.TrackVector).all()
    if len(all_tv) < 2:
        return None, None

    ids = np.array([v.track_id for v in all_tv])
    matrix = np.array([v.feature_vector for v in all_tv], dtype=dtype)

    norm = db.get(models.VectorNormParams, 1)
    if norm:
        means = np.array(norm.means, dtype=dtype)
        stds = np.array(norm.stds, dtype=dtype)
        stds[stds == 0] = 1.0
        matrix = (matrix - means) / stds

    matrix *= user_weight_vector(user, dtype=dtype)

    row_norms = np.linalg.norm(matrix, axis=1, keepdims=True)
    row_norms[row_norms == 0] = 1.0
    matrix /= row_norms

    return ids, matrix


def enrich_tracks(db: Session, ids) -> dict[int, dict]:
    """Map track id → enriched dict (album/artist joined) for the given ids.

    Fields match what ``playTrack()`` requires on the web client.
    """
    ids = list(ids)
    if not ids:
        return {}
    rows = db.execute(_ENRICH_SQL, {"ids": ids}).fetchall()
    return {row.id: dict(row._mapping) for row in rows}
