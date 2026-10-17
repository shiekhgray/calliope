"""Music Map endpoints.

Serves the fixed 2-D atlas (computed offline by the indexer from the PANNs audio
embedding) plus the 3-PC gestalt color lens computed on demand. All heavy
reduction stays server-side; the client only ever receives coordinates and
color values.

See prd/music-map.md, prd/map-embedding-rebase.md.
"""
import numpy as np
from fastapi import APIRouter, Depends
from sqlalchemy import text
from sqlalchemy.orm import Session

from app import models
from app.auth import get_current_user
from app.database import get_db

router = APIRouter(prefix="/map", tags=["map"])


def _load_matrix(db: Session):
    """Return (ids, L2-normalized embedding matrix) for all embedded tracks.

    Mirrors the embedding similarity engine: plain L2-normalize, no z-score and
    no weights (a learned embedding has no weight-groups).
    """
    all_e = (
        db.query(models.TrackVectorEmbed)
        .order_by(models.TrackVectorEmbed.track_id)
        .all()
    )
    if len(all_e) < 2:
        return None, None
    ids = np.array([e.track_id for e in all_e])
    matrix = np.array([e.embedding for e in all_e], dtype=np.float64)
    norms = np.linalg.norm(matrix, axis=1, keepdims=True)
    norms[norms == 0] = 1.0
    return ids, matrix / norms


@router.get("")
def get_map(
    db: Session = Depends(get_db),
    _user: models.User = Depends(get_current_user),
):
    """All atlas points with hover-tooltip metadata and default cluster color."""
    rows = db.execute(text("""
        SELECT mc.track_id, mc.x, mc.y, mc.cluster_id,
               t.title AS track_title, t.album_id,
               al.title AS album_title,
               ar.id AS artist_id, ar.name AS artist_name
        FROM track_map_coords mc
        JOIN tracks t   ON t.id = mc.track_id
        JOIN albums al  ON al.id = t.album_id
        JOIN artists ar ON ar.id = al.artist_id
        ORDER BY mc.track_id
    """)).fetchall()
    return [dict(r._mapping) for r in rows]


@router.get("/pca")
def map_pca(
    db: Session = Depends(get_db),
    _user: models.User = Depends(get_current_user),
):
    """3-PC gestalt: top 3 principal components → per-track [r,g,b] in 0–1.

    A whole-shape-at-a-glance overview, not a quantitative readout.
    """
    ids, matrix = _load_matrix(db)
    if ids is None:
        return {}

    centered = matrix - matrix.mean(axis=0, keepdims=True)
    # Top-3 right singular vectors are the principal axes.
    _, _, vt = np.linalg.svd(centered, full_matrices=False)
    proj = centered @ vt[:3].T  # (N, 3)

    lo = proj.min(axis=0, keepdims=True)
    span = (proj.max(axis=0, keepdims=True) - lo)
    span[span == 0] = 1.0
    rgb = (proj - lo) / span
    return {int(tid): [round(float(c), 4) for c in rgb[i]] for i, tid in enumerate(ids)}
