from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.database import get_db
from app import models

router = APIRouter(prefix="/genres", tags=["genres"])


@router.get("")
def list_genres(db: Session = Depends(get_db)):
    return db.query(models.Genre).order_by(models.Genre.name).all()
