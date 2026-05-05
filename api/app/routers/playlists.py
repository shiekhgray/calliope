import numpy as np
from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.auth import get_current_user
from app.database import get_db
from app import models

router = APIRouter(prefix="/playlists", tags=["playlists"])

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


class PlaylistCreate(BaseModel):
    title: str
    description: str | None = None


class PlaylistUpdate(BaseModel):
    title: str | None = None
    description: str | None = None


class TrackAdd(BaseModel):
    track_id: int


class ReorderBody(BaseModel):
    track_ids: list[int]


@router.get("")
def list_playlists(db: Session = Depends(get_db)):
    return db.query(models.Playlist).order_by(models.Playlist.created_at).all()


@router.get("/{playlist_id}")
def get_playlist(playlist_id: int, db: Session = Depends(get_db)):
    pl = db.get(models.Playlist, playlist_id)
    if not pl:
        raise HTTPException(status_code=404)
    return {
        "id": pl.id,
        "title": pl.title,
        "description": pl.description,
        "owner_id": pl.owner_id,
        "created_at": pl.created_at,
        "entries": [
            {
                "id": e.id,
                "position": e.position,
                "track": {
                    "id": e.track.id,
                    "title": e.track.title,
                    "track_number": e.track.track_number,
                    "duration_ms": e.track.duration_ms,
                    "bitrate_kbps": e.track.bitrate_kbps,
                    "format": e.track.format,
                    "album_id": e.track.album_id,
                    "album_title": e.track.album.title,
                    "artist_id": e.track.album.artist_id,
                    "artist_name": e.track.album.artist.name,
                },
            }
            for e in pl.entries
        ],
    }


@router.post("", status_code=201)
def create_playlist(
    body: PlaylistCreate,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    pl = models.Playlist(owner_id=current_user.id, title=body.title, description=body.description)
    db.add(pl)
    db.commit()
    db.refresh(pl)
    return pl


@router.put("/{playlist_id}")
def update_playlist(
    playlist_id: int,
    body: PlaylistUpdate,
    db: Session = Depends(get_db),
    _current_user: models.User = Depends(get_current_user),
):
    pl = db.get(models.Playlist, playlist_id)
    if not pl:
        raise HTTPException(status_code=404)
    if body.title is not None:
        pl.title = body.title
    if body.description is not None:
        pl.description = body.description
    db.commit()
    db.refresh(pl)
    return pl


@router.delete("/{playlist_id}", status_code=204)
def delete_playlist(
    playlist_id: int,
    db: Session = Depends(get_db),
    _current_user: models.User = Depends(get_current_user),
):
    pl = db.get(models.Playlist, playlist_id)
    if not pl:
        raise HTTPException(status_code=404)
    db.delete(pl)
    db.commit()


@router.post("/{playlist_id}/tracks", status_code=201)
def add_track(
    playlist_id: int,
    body: TrackAdd,
    db: Session = Depends(get_db),
    _current_user: models.User = Depends(get_current_user),
):
    pl = db.get(models.Playlist, playlist_id)
    if not pl:
        raise HTTPException(status_code=404)
    max_pos = max((e.position for e in pl.entries), default=-1)
    entry = models.PlaylistTrack(
        playlist_id=playlist_id, track_id=body.track_id, position=max_pos + 1
    )
    db.add(entry)
    db.commit()
    db.refresh(entry)
    return entry


@router.delete("/{playlist_id}/tracks/{track_id}", status_code=204)
def remove_track(
    playlist_id: int,
    track_id: int,
    db: Session = Depends(get_db),
    _current_user: models.User = Depends(get_current_user),
):
    entry = (
        db.query(models.PlaylistTrack)
        .filter_by(playlist_id=playlist_id, track_id=track_id)
        .first()
    )
    if not entry:
        raise HTTPException(status_code=404)
    db.delete(entry)
    db.commit()


@router.put("/{playlist_id}/tracks/reorder")
def reorder_tracks(
    playlist_id: int,
    body: ReorderBody,
    db: Session = Depends(get_db),
    _current_user: models.User = Depends(get_current_user),
):
    entries = {e.track_id: e for e in db.query(models.PlaylistTrack).filter_by(playlist_id=playlist_id).all()}
    for pos, track_id in enumerate(body.track_ids):
        if track_id in entries:
            entries[track_id].position = pos
    db.commit()
    return {"ok": True}


@router.get("/{playlist_id}/similar")
def similar_to_playlist(
    playlist_id: int,
    limit: int = Query(default=10, ge=1, le=100),
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    # 1. Fetch the playlist
    pl = db.get(models.Playlist, playlist_id)
    if not pl:
        raise HTTPException(status_code=404)

    # 2. All track_ids ordered by position; seed pool = last min(10, len) entries
    ordered_track_ids = [e.track_id for e in pl.entries]  # already ordered by position
    if not ordered_track_ids:
        return []
    seed_pool = ordered_track_ids[-min(10, len(ordered_track_ids)):]

    # 3. Seed pool is empty → already handled above (ordered_track_ids empty check)

    # 4. Query track_vectors for seed track_ids via ORM (raw SQL returns pgvector as a string)
    seed_id_set = list(set(seed_pool))
    tv_rows = db.query(models.TrackVector).filter(
        models.TrackVector.track_id.in_(seed_id_set)
    ).all()
    vec_map = {row.track_id: np.array(row.feature_vector, dtype=np.float32) for row in tv_rows}

    # Build vector list: iterate seed_pool in order, append vector if it exists (duplicates count twice)
    seed_vectors = [vec_map[tid] for tid in seed_pool if tid in vec_map]

    # 5. Fewer than 2 vectors → return []
    if len(seed_vectors) < 2:
        return []

    # 6. Get norm params
    norm = db.get(models.VectorNormParams, 1)
    if norm is None:
        return []

    means = np.array(norm.means, dtype=np.float32)
    stds = np.array(norm.stds, dtype=np.float32)
    stds[stds == 0] = 1.0

    # 7. Normalize each seed vector
    normalized = [(v - means) / stds for v in seed_vectors]

    # 8. Apply per-user weights
    weights = np.ones(60, dtype=np.float32)
    for group, sl in DIM_SLICES.items():
        col = f"sim_weight_{group}"
        w = float(getattr(current_user, col, 5))
        weights[sl] *= w / 5.0
    weighted = [v * weights for v in normalized]

    # 9. Compute centroid
    stack = np.stack(weighted, axis=0)
    centroid = np.mean(stack, axis=0)

    # 10. L2-normalize the centroid
    centroid_norm = np.linalg.norm(centroid)
    if centroid_norm == 0:
        centroid_norm = 1.0
    centroid /= centroid_norm

    # 11. Set of all track_ids in the playlist (for deduplication)
    playlist_track_set = set(ordered_track_ids)

    # 12. Fetch all indexed tracks and compute cosine similarity to centroid
    all_tv = db.query(models.TrackVector).all()
    if len(all_tv) < 2:
        return []

    ids = np.array([v.track_id for v in all_tv])
    matrix = np.array([v.feature_vector for v in all_tv], dtype=np.float32)

    matrix = (matrix - means) / stds
    matrix *= weights
    row_norms = np.linalg.norm(matrix, axis=1, keepdims=True)
    row_norms[row_norms == 0] = 1.0
    matrix /= row_norms

    sims = matrix @ centroid

    # Exclude tracks already in the playlist
    for i, tid in enumerate(ids):
        if tid in playlist_track_set:
            sims[i] = -2.0

    # Take top limit*3 then slice to limit
    fetch_count = min(limit * 3, len(sims))
    top_idx = np.argpartition(sims, -fetch_count)[-fetch_count:]
    top_idx = top_idx[np.argsort(sims[top_idx])[::-1]]
    top_ids = ids[top_idx].tolist()[:limit]

    if not top_ids:
        return []

    # 13. Fetch track details with joins
    rows = db.execute(
        text("""
            SELECT t.id, t.title, t.track_number, t.duration_ms, t.file_path,
                   t.format, t.play_count, t.album_id,
                   al.title AS album_title, ar.id AS artist_id, ar.name AS artist_name
            FROM tracks t
            JOIN albums al ON al.id = t.album_id
            JOIN artists ar ON ar.id = al.artist_id
            WHERE t.id = ANY(:ids)
        """),
        {"ids": top_ids},
    ).fetchall()

    track_map = {row.id: dict(row._mapping) for row in rows}
    return [track_map[tid] for tid in top_ids if tid in track_map]
