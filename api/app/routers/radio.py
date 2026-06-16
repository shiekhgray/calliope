"""Radio continuation — POST /radio/next.

One mode-agnostic endpoint that keeps all vector math + per-user Sound Matching
weights server-side. The client owns the ephemeral session state (anchor, last,
played set, radius) and passes it in on every call; the server returns one
enriched next track plus the updated radius to echo back.

All geometry happens in the user's weighted, z-scored, L2-normalized space
(see app.similarity). "Distance" is cosine distance = 1 - cosine_similarity.

Modes:
  classic          random walk — nearest unplayed to the track that just finished.
  anchor           nearest to the midpoint between the session anchor and last.
  ripple           journey outward — nearest track farther from the seed than the
                   growing radius.
  anchored_ripple  anchor tether + soft outward radius + consecutive-cohesion cap.

The cohesion cap (anchor/ripple/anchored_ripple) keeps back-to-back tracks close:
candidates must be within the closest ~quartile of the just-played track. If the
cap empties the candidate set it is dropped rather than stopping radio.
"""
import numpy as np
from fastapi import APIRouter, Depends, HTTPException, Response
from sqlalchemy import text
from sqlalchemy.orm import Session

from app import models
from app.auth import get_current_user
from app.database import get_db
from app.similarity import enrich_tracks, load_weighted_matrix

router = APIRouter(prefix="/radio", tags=["radio"])

VALID_MODES = {"classic", "anchor", "ripple", "anchored_ripple"}

# Fraction of the just-played track's nearest neighbours that pass the cohesion
# cap (tunable — the load-bearing knob for smooth transitions).
COHESION_PERCENTILE = 25.0
# Gentle outward creep of the soft radius per pick in anchored_ripple.
SOFT_RADIUS_STEP = 0.5


def _sample_pick(metric, mask, variety, rng):
    """Pick an index minimizing ``metric`` among ``mask`` rows.

    variety 0 → always the best candidate; higher → sample from the top-K,
    weighted toward the top (top-K temperature). Returns an int index or None.
    """
    cand = np.where(mask)[0]
    if cand.size == 0:
        return None
    order = cand[np.argsort(metric[cand], kind="stable")]
    k = min(1 + max(0, int(variety)), order.size)
    if k <= 1:
        return int(order[0])
    topk = order[:k]
    weights = np.arange(k, 0, -1, dtype=np.float64)  # k, k-1, ..., 1
    weights /= weights.sum()
    return int(rng.choice(topk, p=weights))


@router.post("/next")
def radio_next(
    body: dict,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    mode = body.get("mode", "classic")
    if mode not in VALID_MODES:
        raise HTTPException(status_code=400, detail=f"Unknown radio mode '{mode}'")

    last_id = body.get("last_id")
    if last_id is None:
        raise HTTPException(status_code=400, detail="last_id is required")
    anchor_id = body.get("anchor_id")
    played_ids = set(body.get("played_ids") or [])
    radius = body.get("radius")
    source_album_id = body.get("source_album_id")
    variety = max(0, min(10, int(body.get("variety") or 0)))

    ids, matrix = load_weighted_matrix(db, current_user)
    if ids is None:
        return Response(status_code=204)

    id_to_idx = {int(t): i for i, t in enumerate(ids)}
    if last_id not in id_to_idx:
        raise HTTPException(status_code=404, detail="Track not indexed yet")

    last_idx = id_to_idx[last_id]
    dist_from_last = 1.0 - matrix @ matrix[last_idx]

    # The non-classic modes pin geometry to the session anchor (the track that
    # started the station). On the first extension anchor == last.
    if mode != "classic":
        if anchor_id is None or anchor_id not in id_to_idx:
            raise HTTPException(status_code=404, detail="Anchor track not indexed yet")
        anchor_idx = id_to_idx[anchor_id]
        dist_from_anchor = 1.0 - matrix @ matrix[anchor_idx]

    # Exclusions: the just-played track, the session-played set, and every track
    # on the album that was playing when radio kicked in.
    exclude = np.zeros(len(ids), dtype=bool)
    exclude[last_idx] = True
    if played_ids:
        exclude |= np.isin(ids, list(played_ids))
    if source_album_id is not None:
        alb_rows = db.execute(
            text("SELECT id FROM tracks WHERE album_id = :a"),
            {"a": source_album_id},
        ).fetchall()
        alb_ids = [r[0] for r in alb_rows]
        if alb_ids:
            exclude |= np.isin(ids, alb_ids)
    avail = ~exclude
    if not avail.any():
        return Response(status_code=204)

    rng = np.random.default_rng()
    new_radius = radius

    if mode == "classic":
        chosen = _sample_pick(dist_from_last, avail, variety, rng)
    else:
        # Cohesion cap: keep the next track among the closest quartile to the
        # one that just played. Computed over the still-available candidates.
        cap = float(np.percentile(dist_from_last[avail], COHESION_PERCENTILE))
        cohesive = avail & (dist_from_last <= cap)

        if mode == "anchor":
            q = matrix[anchor_idx] + matrix[last_idx]
            qn = np.linalg.norm(q) or 1.0
            metric = 1.0 - matrix @ (q / qn)
            chosen = _sample_pick(metric, cohesive, variety, rng)
            if chosen is None:  # cap emptied the list — relax it
                chosen = _sample_pick(metric, avail, variety, rng)

        elif mode == "ripple":
            r = float(radius) if radius is not None else -1.0
            outward = avail & (dist_from_anchor > r)
            metric = dist_from_anchor  # nearest beyond the current radius
            chosen = _sample_pick(metric, outward & cohesive, variety, rng)
            if chosen is None:
                chosen = _sample_pick(metric, outward, variety, rng)
            if chosen is not None:
                new_radius = float(dist_from_anchor[chosen])

        else:  # anchored_ripple
            r = float(radius) if radius is not None else -1.0
            outward = avail & (dist_from_anchor > r)
            q = matrix[anchor_idx] + matrix[last_idx]
            qn = np.linalg.norm(q) or 1.0
            metric = 1.0 - matrix @ (q / qn)
            chosen = _sample_pick(metric, outward & cohesive, variety, rng)
            if chosen is None:
                chosen = _sample_pick(metric, outward, variety, rng)
            if chosen is not None:
                base = r if r >= 0 else 0.0
                new_radius = max(base, SOFT_RADIUS_STEP * float(dist_from_anchor[chosen]))

    if chosen is None:
        return Response(status_code=204)

    chosen_id = int(ids[chosen])
    track = enrich_tracks(db, [chosen_id]).get(chosen_id)
    if track is None:
        return Response(status_code=204)

    return {"track": track, "radius": new_radius}
