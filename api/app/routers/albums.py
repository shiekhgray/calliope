import mimetypes
import os
from pathlib import Path

from fastapi import APIRouter, Body, Depends, HTTPException, UploadFile
from fastapi.responses import FileResponse
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.config import settings
from app.database import get_db
from app import models
from app.auth import get_current_user

router = APIRouter(prefix="/albums", tags=["albums"])


@router.get("/{album_id}")
def get_album(album_id: int, db: Session = Depends(get_db)):
    album = db.get(models.Album, album_id)
    if not album:
        raise HTTPException(status_code=404)

    # Fetch all track credits for this album in one query
    credit_rows = db.execute(text("""
        SELECT tc.track_id, tc.artist_id, ar.name AS artist_name
        FROM track_credits tc
        JOIN artists ar ON ar.id = tc.artist_id
        WHERE tc.track_id IN (
            SELECT id FROM tracks WHERE album_id = :album_id
        )
    """), {"album_id": album_id}).fetchall()

    credits_by_track: dict[int, list[dict]] = {}
    for row in credit_rows:
        credits_by_track.setdefault(row.track_id, []).append(
            {"artist_id": row.artist_id, "artist_name": row.artist_name}
        )

    return {
        "id": album.id,
        "title": album.title,
        "year": album.year,
        "cover_art_path": album.cover_art_path,
        "album_type": album.album_type,
        "artist_id": album.artist_id,
        "artist_name": album.artist.name,
        "tracks": [
            {
                "id": t.id,
                "title": t.title,
                "track_number": t.track_number,
                "duration_ms": t.duration_ms,
                "bitrate_kbps": t.bitrate_kbps,
                "format": t.format,
                "play_count": t.play_count,
                "credits": credits_by_track.get(t.id, []),
            }
            for t in album.tracks
        ],
    }


@router.put("/{album_id}/art")
async def upload_album_art(
    album_id: int,
    file: UploadFile,
    db: Session = Depends(get_db),
    _user=Depends(get_current_user),
):
    album = db.get(models.Album, album_id)
    if not album:
        raise HTTPException(status_code=404)

    if not file.content_type or not file.content_type.startswith("image/"):
        raise HTTPException(status_code=422, detail="File must be an image")

    # Derive album directory from the first track
    if not album.tracks:
        raise HTTPException(status_code=422, detail="Album has no tracks — cannot determine directory")

    album_dir = Path(settings.music_root) / Path(album.tracks[0].file_path).parent
    dest = album_dir / "Folder.jpg"

    content = await file.read()
    dest.write_bytes(content)

    rel_path = str(Path(album.tracks[0].file_path).parent / "Folder.jpg")
    album.cover_art_path = rel_path
    db.commit()

    return {"cover_art_path": rel_path}


_VALID_ALBUM_TYPES = {"album", "ep", "single"}


@router.patch("/{album_id}/type")
def set_album_type(
    album_id: int,
    album_type: str = Body(..., embed=True),
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user),
):
    if current_user.id != 1:
        raise HTTPException(status_code=403, detail="Owner only")
    if album_type not in _VALID_ALBUM_TYPES:
        raise HTTPException(status_code=400, detail="album_type must be 'album', 'ep', or 'single'")
    album = db.get(models.Album, album_id)
    if not album:
        raise HTTPException(status_code=404)
    album.album_type = album_type
    db.commit()
    db.refresh(album)
    return {
        "id": album.id,
        "title": album.title,
        "year": album.year,
        "cover_art_path": album.cover_art_path,
        "album_type": album.album_type,
        "artist_id": album.artist_id,
        "artist_name": album.artist.name,
    }


@router.get("/{album_id}/art")
def get_album_art(album_id: int, db: Session = Depends(get_db)):
    album = db.get(models.Album, album_id)
    if not album or not album.cover_art_path:
        raise HTTPException(status_code=404)

    art_path = Path(settings.music_root) / album.cover_art_path
    if not art_path.is_file():
        raise HTTPException(status_code=404)

    media_type = mimetypes.guess_type(str(art_path))[0] or "image/jpeg"
    return FileResponse(
        str(art_path),
        media_type=media_type,
        headers={"Cache-Control": "public, max-age=31536000, immutable"},
    )
