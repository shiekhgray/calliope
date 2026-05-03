import mimetypes
import os
from pathlib import Path

import numpy as np
from fastapi import APIRouter, Depends, HTTPException, Query, Request
from fastapi.responses import Response, StreamingResponse
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.config import settings
from app.database import get_db
from app import models
from app.auth import get_current_user

router = APIRouter(prefix="/tracks", tags=["tracks"])

CHUNK_SIZE = 1024 * 512  # 512 KB


@router.get("")
def list_tracks(
    sort: str = Query(default="play_count"),
    limit: int = Query(default=50, ge=1, le=200),
    db: Session = Depends(get_db),
    _user=Depends(get_current_user),
):
    rows = db.execute(
        text("""
            SELECT t.id, t.title, t.track_number, t.duration_ms, t.bitrate_kbps,
                   t.format, t.play_count, t.album_id,
                   al.title AS album_title, ar.id AS artist_id, ar.name AS artist_name
            FROM tracks t
            JOIN albums al ON al.id = t.album_id
            JOIN artists ar ON ar.id = al.artist_id
            ORDER BY t.play_count DESC
            LIMIT :limit
        """),
        {"limit": limit},
    ).fetchall()
    return [dict(row._mapping) for row in rows]


@router.get("/{track_id}/stream")
def stream_track(track_id: int, request: Request, db: Session = Depends(get_db)):
    track = db.get(models.Track, track_id)
    if not track:
        raise HTTPException(status_code=404)

    path = Path(settings.music_root) / track.file_path
    if not path.is_file():
        raise HTTPException(status_code=404)

    file_size = path.stat().st_size
    media_type = mimetypes.guess_type(str(path))[0] or "application/octet-stream"

    range_header = request.headers.get("Range")
    if range_header:
        start, end = _parse_range(range_header, file_size)
        length = end - start + 1

        def iter_file():
            with open(path, "rb") as f:
                f.seek(start)
                remaining = length
                while remaining > 0:
                    chunk = f.read(min(CHUNK_SIZE, remaining))
                    if not chunk:
                        break
                    remaining -= len(chunk)
                    yield chunk

        return StreamingResponse(
            iter_file(),
            status_code=206,
            media_type=media_type,
            headers={
                "Content-Range": f"bytes {start}-{end}/{file_size}",
                "Content-Length": str(length),
                "Accept-Ranges": "bytes",
            },
        )

    def iter_full():
        with open(path, "rb") as f:
            while chunk := f.read(CHUNK_SIZE):
                yield chunk

    return StreamingResponse(
        iter_full(),
        media_type=media_type,
        headers={
            "Content-Length": str(file_size),
            "Accept-Ranges": "bytes",
        },
    )


@router.post("/{track_id}/played")
def mark_played(
    track_id: int,
    db: Session = Depends(get_db),
    _user=Depends(get_current_user),
):
    track = db.get(models.Track, track_id)
    if not track:
        raise HTTPException(status_code=404)
    track.play_count += 1
    db.commit()
    return {"play_count": track.play_count}


@router.get("/{track_id}/similar")
def similar_tracks(
    track_id: int,
    limit: int = Query(default=25, ge=1, le=100),
    db: Session = Depends(get_db),
    _user=Depends(get_current_user),
):
    tv = db.query(models.TrackVector).filter_by(track_id=track_id).first()
    if not tv:
        raise HTTPException(status_code=404, detail="Track not indexed yet")

    all_tv = db.query(models.TrackVector).all()
    if len(all_tv) < 2:
        return []

    ids = np.array([v.track_id for v in all_tv])
    matrix = np.array([v.feature_vector for v in all_tv], dtype=np.float32)

    norm = db.get(models.VectorNormParams, 1)
    if norm:
        means = np.array(norm.means, dtype=np.float32)
        stds = np.array(norm.stds, dtype=np.float32)
        stds[stds == 0] = 1.0
        matrix = (matrix - means) / stds

    row_norms = np.linalg.norm(matrix, axis=1, keepdims=True)
    row_norms[row_norms == 0] = 1.0
    matrix /= row_norms

    query_mask = ids == track_id
    query_vec = matrix[query_mask][0]
    sims = matrix @ query_vec
    sims[query_mask] = -2.0

    actual_limit = min(limit, len(sims) - 1)
    top_idx = np.argpartition(sims, -actual_limit)[-actual_limit:]
    top_idx = top_idx[np.argsort(sims[top_idx])[::-1]]
    top_ids = ids[top_idx].tolist()

    if not top_ids:
        return []

    rows = db.execute(
        text("""
            SELECT t.id, t.title, t.track_number, t.duration_ms, t.bitrate_kbps,
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


def _parse_range(header: str, file_size: int) -> tuple[int, int]:
    unit, _, rng = header.partition("=")
    if unit != "bytes":
        raise HTTPException(status_code=416)
    start_str, _, end_str = rng.partition("-")
    start = int(start_str) if start_str else file_size - int(end_str)
    end = int(end_str) if end_str else file_size - 1
    if start > end or start < 0 or end >= file_size:
        raise HTTPException(status_code=416)
    return start, end
