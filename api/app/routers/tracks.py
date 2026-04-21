import mimetypes
import os
from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import Response, StreamingResponse
from sqlalchemy.orm import Session

from app.config import settings
from app.database import get_db
from app import models
from app.auth import get_current_user

router = APIRouter(prefix="/tracks", tags=["tracks"])

CHUNK_SIZE = 1024 * 512  # 512 KB


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
