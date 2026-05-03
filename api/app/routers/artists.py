from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.database import get_db
from app import models

router = APIRouter(prefix="/artists", tags=["artists"])


@router.get("")
def list_artists(db: Session = Depends(get_db)):
    rows = db.execute(text("""
        SELECT DISTINCT ar.id, ar.name
        FROM artists ar
        WHERE ar.name != 'Various Artists'
          AND (
            EXISTS (SELECT 1 FROM album_artists aa WHERE aa.artist_id = ar.id)
            OR EXISTS (
              SELECT 1 FROM albums al
              WHERE al.artist_id = ar.id
                AND NOT EXISTS (SELECT 1 FROM album_artists aa2 WHERE aa2.album_id = al.id)
            )
          )
        ORDER BY ar.name
    """)).fetchall()
    return [{"id": row.id, "name": row.name} for row in rows]


@router.get("/{artist_id}/albums")
def list_albums(artist_id: int, db: Session = Depends(get_db)):
    artist = db.get(models.Artist, artist_id)
    if not artist:
        raise HTTPException(status_code=404)
    rows = db.execute(text("""
        SELECT DISTINCT al.id, al.title, al.year, al.cover_art_path, al.artist_id, ar2.name AS artist_name
        FROM albums al
        JOIN album_artists aa ON aa.album_id = al.id
        JOIN artists ar2 ON ar2.id = al.artist_id
        WHERE aa.artist_id = :artist_id
        ORDER BY al.year, al.title
    """), {"artist_id": artist_id}).fetchall()
    return [
        {
            "id": row.id,
            "title": row.title,
            "year": row.year,
            "cover_art_path": row.cover_art_path,
            "artist_id": row.artist_id,
            "artist_name": row.artist_name,
        }
        for row in rows
    ]


@router.get("/{artist_id}/compilations")
def list_artist_compilations(artist_id: int, db: Session = Depends(get_db)):
    artist = db.get(models.Artist, artist_id)
    if not artist:
        raise HTTPException(status_code=404)
    rows = db.execute(text("""
        SELECT DISTINCT al.id, al.title, al.year, al.cover_art_path, al.artist_id
        FROM albums al
        JOIN tracks t ON t.album_id = al.id
        JOIN track_credits tc ON tc.track_id = t.id
        WHERE tc.artist_id = :artist_id
          AND NOT EXISTS (
            SELECT 1 FROM album_artists aa
            WHERE aa.album_id = al.id AND aa.artist_id = :artist_id
          )
        ORDER BY al.year, al.title
    """), {"artist_id": artist_id}).fetchall()
    return [
        {
            "id": row.id,
            "title": row.title,
            "year": row.year,
            "cover_art_path": row.cover_art_path,
            "artist_id": row.artist_id,
        }
        for row in rows
    ]


@router.get("/{artist_id}/top-tracks")
def top_tracks(
    artist_id: int,
    limit: int = Query(default=25, ge=1, le=100),
    db: Session = Depends(get_db),
):
    artist = db.get(models.Artist, artist_id)
    if not artist:
        raise HTTPException(status_code=404)
    rows = db.execute(
        text("""
            SELECT DISTINCT t.id, t.title, t.track_number, t.duration_ms, t.bitrate_kbps,
                   t.format, t.play_count, t.album_id,
                   al.title AS album_title, al.artist_id, ar.name AS artist_name
            FROM tracks t
            JOIN albums al ON al.id = t.album_id
            JOIN artists ar ON ar.id = al.artist_id
            WHERE (
                EXISTS (
                    SELECT 1 FROM album_artists aa
                    WHERE aa.album_id = al.id AND aa.artist_id = :artist_id
                )
                OR (
                    al.artist_id = :artist_id
                    AND NOT EXISTS (SELECT 1 FROM album_artists aa WHERE aa.album_id = al.id)
                )
            )
            ORDER BY t.play_count DESC, t.id
            LIMIT :limit
        """),
        {"artist_id": artist_id, "limit": limit},
    ).fetchall()
    return [dict(row._mapping) for row in rows]
