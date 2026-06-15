"""Music Map atlas builder.

Projects the 60-dim feature vectors to fixed 2-D coordinates (UMAP) and computes
a default neutral-weight cluster assignment for each track. Runs offline as a
batch step at the end of indexing, or via the manual POST /map/rebuild trigger.

Design (see prd/music-map.md):
  * Positions are computed ONCE and frozen. A normal rescan only `.transform()`s
    new tracks into the existing embedding, so the geography never scrambles.
  * A full refit (POST /map/rebuild) re-fits the whole library and refreshes the
    pickled model — used after large library growth.
  * Preprocessing mirrors the similarity engine (z-score via vector_norm_params,
    neutral weights) so the atlas faithfully reflects what the engine sees. We
    L2-normalize before the euclidean UMAP fit so distances behave like the
    cosine metric the /similar endpoint uses.
"""
import os
import pickle
import sys
from datetime import datetime
from pathlib import Path

import numpy as np
from sqlalchemy import text
from sqlalchemy.orm import Session

from .models import TrackVector

# Where the fitted UMAP model is pickled (backed by a named docker volume).
MODEL_PATH = Path(os.environ.get("MAP_MODEL_PATH", "/data/umap_model.pkl"))

# KMeans cluster count for the default (neutral-weight) coloring.
N_CLUSTERS = 16


def _zscore_matrix(db: Session, ids, vectors):
    """Z-score the raw feature matrix using the persisted vector_norm_params."""
    matrix = np.array(vectors, dtype=np.float64)
    row = db.execute(text(
        "SELECT means, stds FROM vector_norm_params WHERE id = 1"
    )).fetchone()
    if row:
        means = np.array(row.means, dtype=np.float64)
        stds = np.array(row.stds, dtype=np.float64)
        stds[stds == 0] = 1.0
        matrix = (matrix - means) / stds
    return matrix


def _l2_normalize(matrix):
    norms = np.linalg.norm(matrix, axis=1, keepdims=True)
    norms[norms == 0] = 1.0
    return matrix / norms


def kmeans(matrix, k, seed=42, iters=100):
    """Compact deterministic k-means (k-means++ init). Returns int labels.

    Kept dependency-free and identical in spirit to the API's live recolor
    routine so neutral-weight colors line up between offline and online.
    """
    rng = np.random.default_rng(seed)
    n = matrix.shape[0]
    k = min(k, n)

    # k-means++ seeding
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

    # Stabilize cluster ids: sort by centroid position so colors don't shuffle.
    order = np.argsort(centers[:, 0] + centers[:, 1] * 1e-3)
    remap = {old: new for new, old in enumerate(order)}
    return np.array([remap[l] for l in labels], dtype=int)


def build_map(db: Session, full_refit: bool = False):
    """Build or update the track_map_coords atlas.

    full_refit=True  → fit UMAP on the whole library, repickle the model,
                       recompute every coordinate.
    full_refit=False → transform only tracks missing from track_map_coords into
                       the frozen embedding (cheap incremental update).
    """
    try:
        import umap
    except ImportError:
        print("Mapping: umap-learn not installed; skipping atlas build", file=sys.stderr, flush=True)
        return

    # Query via ORM so the pgvector column deserializes to a list (raw SQL
    # returns the vector as a string).
    rows = db.query(TrackVector).order_by(TrackVector.track_id).all()
    if len(rows) < 3:
        print("Mapping: <3 indexed tracks, skipping atlas", flush=True)
        return

    all_ids = [r.track_id for r in rows]
    all_vecs = [r.feature_vector for r in rows]
    matrix = _l2_normalize(_zscore_matrix(db, all_ids, all_vecs))

    have_model = MODEL_PATH.exists()
    if full_refit or not have_model:
        print(f"Mapping: full UMAP fit on {len(all_ids)} tracks", flush=True)
        reducer = umap.UMAP(
            n_neighbors=15, min_dist=0.1, n_components=2, metric="euclidean",
            random_state=42,
        )
        coords = reducer.fit_transform(matrix)
        MODEL_PATH.parent.mkdir(parents=True, exist_ok=True)
        with open(MODEL_PATH, "wb") as f:
            pickle.dump(reducer, f)
        coord_by_id = {tid: coords[i] for i, tid in enumerate(all_ids)}
    else:
        existing = {
            r.track_id for r in db.execute(text(
                "SELECT track_id FROM track_map_coords"
            )).fetchall()
        }
        new_idx = [i for i, tid in enumerate(all_ids) if tid not in existing]
        if not new_idx:
            print("Mapping: no new tracks to place", flush=True)
            # still refresh clusters below (norms/library may have shifted)
            coord_by_id = {}
        else:
            print(f"Mapping: transforming {len(new_idx)} new tracks", flush=True)
            with open(MODEL_PATH, "rb") as f:
                reducer = pickle.load(f)
            new_coords = reducer.transform(matrix[new_idx])
            coord_by_id = {all_ids[i]: new_coords[n] for n, i in enumerate(new_idx)}

    # Default clusters: full 60-D z-scored + L2 space, neutral weights.
    labels = kmeans(matrix, N_CLUSTERS)
    cluster_by_id = {tid: int(labels[i]) for i, tid in enumerate(all_ids)}

    # Upsert: new tracks get fresh coords; existing tracks keep coords but
    # refresh cluster_id under the latest norms.
    for i, tid in enumerate(all_ids):
        cid = cluster_by_id[tid]
        if tid in coord_by_id:
            x, y = float(coord_by_id[tid][0]), float(coord_by_id[tid][1])
            db.execute(text("""
                INSERT INTO track_map_coords (track_id, x, y, cluster_id, updated_at)
                VALUES (:tid, :x, :y, :cid, :ts)
                ON CONFLICT (track_id) DO UPDATE
                  SET x = EXCLUDED.x, y = EXCLUDED.y,
                      cluster_id = EXCLUDED.cluster_id, updated_at = EXCLUDED.updated_at
            """), {"tid": tid, "x": x, "y": y, "cid": cid, "ts": datetime.utcnow()})
        else:
            db.execute(text("""
                UPDATE track_map_coords
                   SET cluster_id = :cid, updated_at = :ts
                 WHERE track_id = :tid
            """), {"tid": tid, "cid": cid, "ts": datetime.utcnow()})
    db.commit()
    print(f"Mapping: atlas updated ({len(all_ids)} tracks)", flush=True)
