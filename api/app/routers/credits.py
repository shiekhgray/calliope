from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.database import get_db
from app import models
from app.auth import get_current_user

router = APIRouter(tags=["credits"])


class ArtistIdBody(BaseModel):
    artist_id: int


def _require_owner(current_user=Depends(get_current_user)):
    if current_user.id != 1:
        raise HTTPException(status_code=403, detail="Owner only")
    return current_user


def _fetch_album_credits(db: Session, album_id: int) -> list[dict]:
    rows = db.execute(text("""
        SELECT aa.artist_id, ar.name AS artist_name
        FROM album_artists aa
        JOIN artists ar ON ar.id = aa.artist_id
        WHERE aa.album_id = :album_id
        ORDER BY ar.name
    """), {"album_id": album_id}).fetchall()
    return [{"artist_id": row.artist_id, "artist_name": row.artist_name} for row in rows]


def _fetch_track_credits(db: Session, track_id: int) -> list[dict]:
    rows = db.execute(text("""
        SELECT tc.artist_id, ar.name AS artist_name
        FROM track_credits tc
        JOIN artists ar ON ar.id = tc.artist_id
        WHERE tc.track_id = :track_id
        ORDER BY ar.name
    """), {"track_id": track_id}).fetchall()
    return [{"artist_id": row.artist_id, "artist_name": row.artist_name} for row in rows]


# ---------------------------------------------------------------------------
# Album artist credits
# ---------------------------------------------------------------------------

@router.get("/albums/{album_id}/artists")
def get_album_artists(
    album_id: int,
    db: Session = Depends(get_db),
):
    album = db.get(models.Album, album_id)
    if not album:
        raise HTTPException(status_code=404, detail="Album not found")
    return _fetch_album_credits(db, album_id)


@router.post("/albums/{album_id}/artists")
def add_album_artist(
    album_id: int,
    body: ArtistIdBody,
    db: Session = Depends(get_db),
    _user=Depends(_require_owner),
):
    album = db.get(models.Album, album_id)
    if not album:
        raise HTTPException(status_code=404, detail="Album not found")

    artist = db.get(models.Artist, body.artist_id)
    if not artist:
        raise HTTPException(status_code=404, detail="Artist not found")

    existing = db.execute(text("""
        SELECT 1 FROM album_artists WHERE album_id = :album_id AND artist_id = :artist_id
    """), {"album_id": album_id, "artist_id": body.artist_id}).first()
    if existing:
        raise HTTPException(status_code=409, detail="Credit already exists")

    db.execute(text("""
        INSERT INTO album_artists (album_id, artist_id) VALUES (:album_id, :artist_id)
    """), {"album_id": album_id, "artist_id": body.artist_id})
    db.commit()

    return _fetch_album_credits(db, album_id)


@router.delete("/albums/{album_id}/artists/{artist_id}")
def remove_album_artist(
    album_id: int,
    artist_id: int,
    db: Session = Depends(get_db),
    _user=Depends(_require_owner),
):
    album = db.get(models.Album, album_id)
    if not album:
        raise HTTPException(status_code=404, detail="Album not found")

    existing = db.execute(text("""
        SELECT 1 FROM album_artists WHERE album_id = :album_id AND artist_id = :artist_id
    """), {"album_id": album_id, "artist_id": artist_id}).first()
    if not existing:
        raise HTTPException(status_code=404, detail="Credit not found")

    db.execute(text("""
        DELETE FROM album_artists WHERE album_id = :album_id AND artist_id = :artist_id
    """), {"album_id": album_id, "artist_id": artist_id})
    db.commit()

    return {"ok": True}


# ---------------------------------------------------------------------------
# Track credits
# ---------------------------------------------------------------------------

@router.post("/tracks/{track_id}/credits")
def add_track_credit(
    track_id: int,
    body: ArtistIdBody,
    db: Session = Depends(get_db),
    _user=Depends(_require_owner),
):
    track = db.get(models.Track, track_id)
    if not track:
        raise HTTPException(status_code=404, detail="Track not found")

    artist = db.get(models.Artist, body.artist_id)
    if not artist:
        raise HTTPException(status_code=404, detail="Artist not found")

    existing = db.execute(text("""
        SELECT 1 FROM track_credits WHERE track_id = :track_id AND artist_id = :artist_id
    """), {"track_id": track_id, "artist_id": body.artist_id}).first()
    if existing:
        raise HTTPException(status_code=409, detail="Credit already exists")

    db.execute(text("""
        INSERT INTO track_credits (track_id, artist_id) VALUES (:track_id, :artist_id)
    """), {"track_id": track_id, "artist_id": body.artist_id})
    db.commit()

    return _fetch_track_credits(db, track_id)


@router.delete("/tracks/{track_id}/credits/{artist_id}")
def remove_track_credit(
    track_id: int,
    artist_id: int,
    db: Session = Depends(get_db),
    _user=Depends(_require_owner),
):
    track = db.get(models.Track, track_id)
    if not track:
        raise HTTPException(status_code=404, detail="Track not found")

    existing = db.execute(text("""
        SELECT 1 FROM track_credits WHERE track_id = :track_id AND artist_id = :artist_id
    """), {"track_id": track_id, "artist_id": artist_id}).first()
    if not existing:
        raise HTTPException(status_code=404, detail="Credit not found")

    db.execute(text("""
        DELETE FROM track_credits WHERE track_id = :track_id AND artist_id = :artist_id
    """), {"track_id": track_id, "artist_id": artist_id})
    db.commit()

    return {"ok": True}
