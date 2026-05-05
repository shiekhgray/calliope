from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.database import get_db
from app import models

router = APIRouter(prefix="/genres", tags=["genres"])


@router.get("")
def list_genres(
    q: str = Query(default=""),
    db: Session = Depends(get_db),
):
    query = db.query(models.Genre).order_by(models.Genre.name)
    if q:
        query = query.filter(models.Genre.name.ilike(f"%{q}%")).limit(20)
    return query.all()
