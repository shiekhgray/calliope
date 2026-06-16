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
from app.similarity import enrich_tracks, load_weighted_matrix

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
    current_user: models.User = Depends(get_current_user),
):
    tv = db.query(models.TrackVector).filter_by(track_id=track_id).first()
    if not tv:
        raise HTTPException(status_code=404, detail="Track not indexed yet")

    ids, matrix = load_weighted_matrix(db, current_user)
    if ids is None:
        return []

    query_mask = ids == track_id
    query_vec = matrix[query_mask][0]
    sims = matrix @ query_vec
    sims[query_mask] = -2.0

    actual_limit = min(limit, len(sims) - 1)
    top_idx = np.argpartition(sims, -actual_limit)[-actual_limit:]
    top_idx = top_idx[np.argsort(sims[top_idx])[::-1]]
    top_ids = ids[top_idx].tolist()

    track_map = enrich_tracks(db, top_ids)
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
