from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import func
from sqlalchemy.orm import Session

from app.database import get_db
from app import models
from app.models import Album, Track

router = APIRouter(prefix="/artists", tags=["artists"])


@router.get("")
def list_artists(db: Session = Depends(get_db)):
    return (
        db.query(models.Artist)
        .filter(models.Artist.name != "Various Artists")
        .order_by(models.Artist.name)
        .all()
    )


@router.get("/{artist_id}/albums")
def list_albums(artist_id: int, db: Session = Depends(get_db)):
    artist = db.get(models.Artist, artist_id)
    if not artist:
        raise HTTPException(status_code=404)
    albums = (
        db.query(models.Album)
        .filter(models.Album.artist_id == artist_id)
        .order_by(models.Album.year, models.Album.title)
        .all()
    )
    return [
        {
            "id": a.id,
            "title": a.title,
            "year": a.year,
            "cover_art_path": a.cover_art_path,
            "artist_id": a.artist_id,
            "artist_name": artist.name,
        }
        for a in albums
    ]


@router.get("/{artist_id}/compilations")
def list_artist_compilations(artist_id: int, db: Session = Depends(get_db)):
    artist = db.get(models.Artist, artist_id)
    if not artist:
        raise HTTPException(status_code=404)
    va = db.query(models.Artist).filter_by(name="Various Artists").first()
    if not va:
        return []
    albums = (
        db.query(models.Album)
        .join(models.Track, models.Track.album_id == models.Album.id)
        .filter(
            models.Album.artist_id == va.id,
            models.Track.track_artist_id == artist_id,
        )
        .distinct()
        .order_by(models.Album.year, models.Album.title)
        .all()
    )
    return [
        {
            "id": a.id,
            "title": a.title,
            "year": a.year,
            "cover_art_path": a.cover_art_path,
            "artist_id": va.id,
            "artist_name": va.name,
        }
        for a in albums
    ]


@router.get("/{artist_id}/top-tracks")
def top_tracks(artist_id: int, db: Session = Depends(get_db)):
    artist = db.get(models.Artist, artist_id)
    if not artist:
        raise HTTPException(status_code=404)
    tracks = (
        db.query(Track)
        .join(Album, Track.album_id == Album.id)
        .filter(Album.artist_id == artist_id)
        .order_by(Track.play_count.desc(), func.random())
        .limit(10)
        .all()
    )
    return [
        {
            "id": t.id,
            "title": t.title,
            "track_number": t.track_number,
            "duration_ms": t.duration_ms,
            "bitrate_kbps": t.bitrate_kbps,
            "format": t.format,
            "play_count": t.play_count,
            "album_id": t.album_id,
            "album_title": t.album.title,
            "artist_id": artist_id,
            "artist_name": artist.name,
        }
        for t in tracks
    ]
