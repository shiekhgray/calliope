import json
import logging
import time
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime

logger = logging.getLogger(__name__)

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException
from sqlalchemy import func
from sqlalchemy.orm import Session

from app import models
from app.auth import get_current_user
from app.database import SessionLocal, get_db

router = APIRouter(prefix="/discover", tags=["discover"])

_refresh_running = False
_last_refreshed: datetime | None = None


def _query_itunes(artist_name: str) -> list[dict] | None:
    """
    Returns a list of album results, or None if the request failed.
    (Empty list means iTunes returned no results for this artist.)
    Retries once with backoff on rate-limit (429) responses.
    """
    term = urllib.parse.quote(artist_name)
    url = f"https://itunes.apple.com/search?term={term}&entity=album&limit=50&media=music"
    for attempt in range(2):
        try:
            req = urllib.request.Request(url, headers={"User-Agent": "Calliope/2.0"})
            with urllib.request.urlopen(req, timeout=10) as resp:
                data = json.loads(resp.read())
            return [r for r in data.get("results", []) if r.get("wrapperType") == "collection"]
        except urllib.error.HTTPError as e:
            if e.code == 429 and attempt == 0:
                logger.warning("iTunes rate limited for %r, backing off 30s…", artist_name)
                time.sleep(30)
                continue
            logger.error("iTunes HTTP %s for artist %r", e.code, artist_name)
            return None
        except Exception as e:
            logger.error("iTunes request failed for artist %r: %s", artist_name, e)
            return None
    return None


def _run_refresh():
    global _refresh_running, _last_refreshed
    _refresh_running = True
    try:
        db: Session = SessionLocal()
        try:
            artists = db.query(models.Artist).order_by(models.Artist.name).all()
            for artist in artists:
                results = _query_itunes(artist.name)
                if results is None:
                    logger.warning("Skipping artist %r due to iTunes query failure", artist.name)
                    continue
                for r in results:
                    collection_id = r.get("collectionId")
                    if not collection_id:
                        continue
                    album_title = r.get("collectionName") or ""
                    # Strip trailing " - Single", " - EP" suffixes iTunes sometimes adds
                    for suffix in (" - Single", " - EP"):
                        if album_title.endswith(suffix):
                            album_title = album_title[: -len(suffix)]
                    release_date = None
                    raw_date = r.get("releaseDate", "")
                    if raw_date:
                        try:
                            from datetime import date
                            release_date = date.fromisoformat(raw_date[:10])
                        except ValueError:
                            pass
                    # Upscale artwork from 100x100 to 300x300
                    artwork_url = (r.get("artworkUrl100") or "").replace("100x100bb", "300x300bb")

                    existing = (
                        db.query(models.Discovery)
                        .filter_by(itunes_collection_id=collection_id)
                        .first()
                    )
                    if existing:
                        existing.album_title = album_title
                        existing.release_date = release_date
                        existing.artwork_url = artwork_url
                    else:
                        db.add(
                            models.Discovery(
                                artist_id=artist.id,
                                itunes_collection_id=collection_id,
                                album_title=album_title,
                                release_date=release_date,
                                artwork_url=artwork_url,
                                dismissed=False,
                            )
                        )
                db.commit()
                time.sleep(0.15)  # ~6 req/s — well within iTunes limits
        finally:
            db.close()
        _last_refreshed = datetime.utcnow()
    finally:
        _refresh_running = False


@router.post("/refresh", status_code=202)
def trigger_refresh(
    background_tasks: BackgroundTasks,
    _current_user: models.User = Depends(get_current_user),
):
    global _refresh_running
    if _refresh_running:
        raise HTTPException(status_code=409, detail="Refresh already in progress")
    background_tasks.add_task(_run_refresh)
    return {"status": "refresh started"}


@router.get("/status")
def refresh_status():
    return {
        "running": _refresh_running,
        "last_refreshed": _last_refreshed.isoformat() if _last_refreshed else None,
    }


@router.get("")
def get_discoveries(artist_id: int | None = None, db: Session = Depends(get_db)):
    q = (
        db.query(models.Discovery)
        .filter_by(dismissed=False)
        .join(models.Artist)
        .order_by(models.Discovery.release_date.desc().nullslast(), models.Artist.name)
    )
    if artist_id is not None:
        q = q.filter(models.Discovery.artist_id == artist_id)
    discoveries = q.all()
    result = []
    for d in discoveries:
        already_owned = (
            db.query(models.Album)
            .filter(
                models.Album.artist_id == d.artist_id,
                func.lower(models.Album.title) == d.album_title.lower(),
            )
            .first()
        )
        if already_owned:
            continue
        result.append(
            {
                "id": d.id,
                "artist_id": d.artist_id,
                "artist_name": d.artist.name,
                "album_title": d.album_title,
                "release_date": d.release_date.isoformat() if d.release_date else None,
                "artwork_url": d.artwork_url,
            }
        )
    return result


@router.post("/{discovery_id}/dismiss", status_code=200)
def dismiss_discovery(
    discovery_id: int,
    db: Session = Depends(get_db),
    _current_user: models.User = Depends(get_current_user),
):
    d = db.query(models.Discovery).filter_by(id=discovery_id).first()
    if not d:
        raise HTTPException(status_code=404, detail="Discovery not found")
    d.dismissed = True
    db.commit()
    return {"ok": True}
