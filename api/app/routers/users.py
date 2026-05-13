from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.auth import get_current_user
from app.database import get_db
from app import models

router = APIRouter(prefix="/users", tags=["users"])


@router.get("")
def list_users(
    db: Session = Depends(get_db),
    _current_user: models.User = Depends(get_current_user),
):
    """Return all users as [{id, username}]. Auth required. No sensitive fields."""
    users = db.query(models.User).order_by(models.User.id).all()
    return [{"id": u.id, "username": u.username} for u in users]
