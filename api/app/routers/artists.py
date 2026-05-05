import json
import logging
import urllib.error
import urllib.parse
import urllib.request

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.config import settings
from app.database import get_db
from app import models

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/artists", tags=["artists"])


def _fetch_lastfm(url: str) -> dict | None:
    """Fire a Last.fm API request. Returns parsed JSON or None on failure."""
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "Calliope/2.0"})
        with urllib.request.urlopen(req, timeout=10) as resp:
            return json.loads(resp.read())
    except Exception as exc:
        logger.warning("Last.fm request failed: %s", exc)
        return None


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
          AND al.album_type = 'album'
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


@router.get("/{artist_id}/singles")
def list_singles(artist_id: int, db: Session = Depends(get_db)):
    artist = db.get(models.Artist, artist_id)
    if not artist:
        raise HTTPException(status_code=404)
    rows = db.execute(text("""
        SELECT DISTINCT
            al.id, al.title, al.year, al.cover_art_path, al.album_type,
            al.artist_id, ar2.name AS artist_name,
            ft.id AS ft_id, ft.title AS ft_title, ft.duration_ms AS ft_duration_ms
        FROM albums al
        JOIN album_artists aa ON aa.album_id = al.id
        JOIN artists ar2 ON ar2.id = al.artist_id
        LEFT JOIN LATERAL (
            SELECT t.id, t.title, t.duration_ms
            FROM tracks t
            WHERE t.album_id = al.id
            ORDER BY t.track_number ASC NULLS LAST, t.id ASC
            LIMIT 1
        ) ft ON true
        WHERE aa.artist_id = :artist_id
          AND al.album_type IN ('single', 'ep')
        ORDER BY al.year DESC NULLS LAST, al.title ASC
    """), {"artist_id": artist_id}).fetchall()
    return [
        {
            "id": row.id,
            "title": row.title,
            "year": row.year,
            "cover_art_path": row.cover_art_path,
            "album_type": row.album_type,
            "artist_id": row.artist_id,
            "artist_name": row.artist_name,
            "first_track": {
                "id": row.ft_id,
                "title": row.ft_title,
                "duration_ms": row.ft_duration_ms,
                "album_id": row.id,
                "album_title": row.title,
                "artist_id": row.artist_id,
                "artist_name": row.artist_name,
            } if row.ft_id is not None else None,
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


@router.get("/{artist_id}/genres/fetch")
def fetch_artist_genres_lastfm(artist_id: int, db: Session = Depends(get_db)):
    """Fetch genre suggestions from Last.fm artist.getTopTags."""
    artist = db.get(models.Artist, artist_id)
    if not artist:
        raise HTTPException(status_code=404, detail="Artist not found")

    if not settings.lastfm_api_key:
        return []

    encoded_name = urllib.parse.quote(artist.name)
    url = (
        f"http://ws.audioscrobbler.com/2.0/"
        f"?method=artist.getTopTags"
        f"&api_key={settings.lastfm_api_key}"
        f"&artist={encoded_name}"
        f"&format=json"
    )

    data = _fetch_lastfm(url)
    if not data:
        return []

    tags = (data.get("toptags") or {}).get("tag", [])
    if not isinstance(tags, list):
        return []

    suggestions = []
    for tag in tags:
        name = tag.get("name", "").strip().lower()
        weight = int(tag.get("count", 0))
        if not name or weight < 10:
            continue
        suggestions.append({"name": name, "source": "lastfm", "weight": weight})
        if len(suggestions) >= 5:
            break

    return suggestions
