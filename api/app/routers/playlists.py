from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.auth import get_current_user
from app.database import get_db
from app import models

router = APIRouter(prefix="/playlists", tags=["playlists"])


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
