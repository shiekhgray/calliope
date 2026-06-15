"""Music Map endpoints.

Serves the fixed 2-D atlas (computed offline by the indexer) plus live,
weight-aware color lenses computed on demand. All heavy reduction/clustering
stays server-side; the client only ever receives coordinates and color values.

See prd/music-map.md.
"""
import numpy as np
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import text
from sqlalchemy.orm import Session

from app import models
from app.auth import get_current_user
from app.database import get_db

router = APIRouter(prefix="/map", tags=["map"])

# Mirror of the similarity engine's grouping (see tracks.py DIM_SLICES).
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

N_CLUSTERS = 16


def _load_matrix(db: Session):
    """Return (ids, z-scored matrix) for all indexed tracks, or (None, None)."""
    all_tv = db.query(models.TrackVector).order_by(models.TrackVector.track_id).all()
    if len(all_tv) < 2:
        return None, None
    ids = np.array([v.track_id for v in all_tv])
    matrix = np.array([v.feature_vector for v in all_tv], dtype=np.float64)

    norm = db.get(models.VectorNormParams, 1)
    if norm:
        means = np.array(norm.means, dtype=np.float64)
        stds = np.array(norm.stds, dtype=np.float64)
        stds[stds == 0] = 1.0
        matrix = (matrix - means) / stds
    return ids, matrix


def _kmeans(matrix, k, seed=42, iters=100):
    """Compact deterministic k-means++ — mirrors indexer/app/mapping.py."""
    rng = np.random.default_rng(seed)
    n = matrix.shape[0]
    k = min(k, n)

    centers = [matrix[rng.integers(n)]]
    for _ in range(1, k):
        d2 = np.min(
            np.array([np.sum((matrix - c) ** 2, axis=1) for c in centers]),
            axis=0,
        )
        total = d2.sum()
        probs = d2 / total if total > 0 else np.full(n, 1.0 / n)
        centers.append(matrix[rng.choice(n, p=probs)])
    centers = np.array(centers)

    labels = np.zeros(n, dtype=int)
    for _ in range(iters):
        dists = np.linalg.norm(matrix[:, None, :] - centers[None, :, :], axis=2)
        new_labels = np.argmin(dists, axis=1)
        if np.array_equal(new_labels, labels):
            break
        labels = new_labels
        for j in range(k):
            members = matrix[labels == j]
            if len(members):
                centers[j] = members.mean(axis=0)

    # Stabilize cluster ids so hues don't shuffle between calls.
    order = np.argsort(centers[:, 0] + centers[:, 1] * 1e-3)
    remap = {old: new for new, old in enumerate(order)}
    return np.array([remap[l] for l in labels], dtype=int)


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


@router.get("/clusters")
def map_clusters(
    weighted: bool = Query(default=True),
    w: str | None = Query(default=None),
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    """Re-cluster all points under the current user's weights (live recolor).

    Reuses the exact /tracks/{id}/similar preprocessing: z-score → per-group
    w/5.0 scaling → L2-normalize → KMeans. Returns {track_id: cluster_id}.

    `w` optionally overrides the saved weights for live preview of unsaved
    slider positions: 9 comma-separated ints in DIM_SLICES order
    (timbre, timbral_variation, harmony, chord_movement, tempo, loudness,
    dynamic_range, brightness, tonal). Falls back to the user's saved weights.
    """
    ids, matrix = _load_matrix(db)
    if ids is None:
        return {}

    if weighted:
        override = None
        if w:
            try:
                parts = [float(p) for p in w.split(",")]
                if len(parts) == len(DIM_SLICES):
                    override = dict(zip(DIM_SLICES.keys(), parts))
            except ValueError:
                override = None
        weights = np.ones(60, dtype=np.float64)
        for group, sl in DIM_SLICES.items():
            val = override[group] if override else float(getattr(current_user, f"sim_weight_{group}", 5))
            weights[sl] *= val / 5.0
        matrix = matrix * weights

    norms = np.linalg.norm(matrix, axis=1, keepdims=True)
    norms[norms == 0] = 1.0
    matrix = matrix / norms

    labels = _kmeans(matrix, N_CLUSTERS)
    return {int(tid): int(labels[i]) for i, tid in enumerate(ids)}


@router.get("/lens")
def map_lens(
    feature: str = Query(...),
    db: Session = Depends(get_db),
    _user: models.User = Depends(get_current_user),
):
    """Single-feature gradient: z-scored group mean per track, min-max 0–1."""
    if feature not in DIM_SLICES:
        raise HTTPException(status_code=400, detail=f"unknown feature '{feature}'")
    ids, matrix = _load_matrix(db)
    if ids is None:
        return {}

    vals = matrix[:, DIM_SLICES[feature]].mean(axis=1)
    lo, hi = float(vals.min()), float(vals.max())
    span = (hi - lo) or 1.0
    scaled = (vals - lo) / span
    return {int(tid): float(scaled[i]) for i, tid in enumerate(ids)}


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
