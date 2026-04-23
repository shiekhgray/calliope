from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import func
from sqlalchemy.orm import Session

from app.database import get_db
from app import models

router = APIRouter(prefix="/compilations", tags=["compilations"])

VARIOUS_ARTISTS = "Various Artists"


def _get_va_artist(db: Session):
    return db.query(models.Artist).filter_by(name=VARIOUS_ARTISTS).first()


@router.get("")
def list_compilations(db: Session = Depends(get_db)):
    va = _get_va_artist(db)
    if not va:
        return []
    albums = (
        db.query(
            models.Album,
            func.count(models.Track.id).label("track_count"),
        )
        .join(models.Track, models.Track.album_id == models.Album.id)
        .filter(models.Album.artist_id == va.id)
        .group_by(models.Album.id)
        .order_by(models.Album.title)
        .all()
    )
    return [
        {
            "id": a.id,
            "title": a.title,
            "year": a.year,
            "cover_art_path": a.cover_art_path,
            "track_count": track_count,
        }
        for a, track_count in albums
    ]
