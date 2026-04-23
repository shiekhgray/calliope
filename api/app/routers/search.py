from fastapi import APIRouter, Depends, Query, Response
from pydantic import BaseModel
from sqlalchemy import func, text
from sqlalchemy.orm import Session

from app.auth import get_current_user
from app.database import get_db
from app import models

router = APIRouter(prefix="/search", tags=["search"])


@router.get("")
def search(q: str = Query(min_length=1), db: Session = Depends(get_db)):
    like = f"%{q}%"
    unaccent_like = func.unaccent(like)
    artists = db.query(models.Artist).filter(func.unaccent(models.Artist.name).ilike(unaccent_like)).limit(20).all()
    albums = db.query(models.Album).filter(func.unaccent(models.Album.title).ilike(unaccent_like)).limit(20).all()
    tracks = db.query(models.Track).filter(func.unaccent(models.Track.title).ilike(unaccent_like)).limit(50).all()

    return {
        "artists": artists,
        "albums": [
            {
                "id": a.id,
                "title": a.title,
                "year": a.year,
                "cover_art_path": a.cover_art_path,
                "artist_id": a.artist_id,
                "artist_name": a.artist.name,
            }
            for a in albums
        ],
        "tracks": [
            {
                "id": t.id,
                "title": t.title,
                "duration_ms": t.duration_ms,
                "bitrate_kbps": t.bitrate_kbps,
                "album_id": t.album_id,
                "album_title": t.album.title,
                "artist_id": t.album.artist_id,
                "artist_name": t.album.artist.name,
            }
            for t in tracks
        ],
    }


@router.get("/history")
def get_history(
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    rows = (
        db.query(models.SearchHistory)
        .filter(models.SearchHistory.user_id == current_user.id)
        .order_by(models.SearchHistory.visited_at.desc())
        .limit(10)
        .all()
    )

    results = []
    for row in rows:
        if row.entity_type == "artist":
            artist = db.query(models.Artist).filter(models.Artist.id == row.entity_id).first()
            if artist:
                results.append({
                    "entity_type": "artist",
                    "entity_id": row.entity_id,
                    "name": artist.name,
                })
        elif row.entity_type == "album":
            album = db.query(models.Album).filter(models.Album.id == row.entity_id).first()
            if album:
                results.append({
                    "entity_type": "album",
                    "entity_id": row.entity_id,
                    "name": album.title,
                    "artist_id": album.artist_id,
                    "artist_name": album.artist.name,
                })
        elif row.entity_type == "track":
            track = db.query(models.Track).filter(models.Track.id == row.entity_id).first()
            if track:
                results.append({
                    "entity_type": "track",
                    "entity_id": row.entity_id,
                    "name": track.title,
                    "album_id": track.album_id,
                    "album_title": track.album.title,
                    "artist_name": track.album.artist.name,
                })

    return results


class HistoryEntry(BaseModel):
    entity_type: str
    entity_id: int


@router.post("/history", status_code=204)
def record_history(
    entry: HistoryEntry,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    # Upsert: insert or update visited_at
    existing = (
        db.query(models.SearchHistory)
        .filter(
            models.SearchHistory.user_id == current_user.id,
            models.SearchHistory.entity_type == entry.entity_type,
            models.SearchHistory.entity_id == entry.entity_id,
        )
        .first()
    )
    if existing:
        existing.visited_at = text("now()")
        # Re-assign to trigger the ORM update
        from datetime import datetime
        existing.visited_at = datetime.utcnow()
    else:
        db.add(models.SearchHistory(
            user_id=current_user.id,
            entity_type=entry.entity_type,
            entity_id=entry.entity_id,
        ))
    db.commit()

    # Prune to 10 most recent
    keep = (
        db.query(models.SearchHistory.id)
        .filter(models.SearchHistory.user_id == current_user.id)
        .order_by(models.SearchHistory.visited_at.desc())
        .limit(10)
        .subquery()
    )
    db.query(models.SearchHistory).filter(
        models.SearchHistory.user_id == current_user.id,
        models.SearchHistory.id.not_in(keep),
    ).delete(synchronize_session=False)
    db.commit()

    return Response(status_code=204)
