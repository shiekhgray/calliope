from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import OAuth2PasswordRequestForm
from jose import JWTError, jwt
from sqlalchemy.orm import Session

from app import models
from app.auth import (
    ALGORITHM,
    create_access_token,
    create_refresh_token,
    get_current_user,
    verify_password,
)
from app.config import settings
from app.database import get_db

router = APIRouter(prefix="/auth", tags=["auth"])


@router.post("/login")
def login(
    form: OAuth2PasswordRequestForm = Depends(),
    db: Session = Depends(get_db),
):
    user = db.query(models.User).filter_by(username=form.username).first()
    if not user or not verify_password(form.password, user.password_hash):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect username or password",
            headers={"WWW-Authenticate": "Bearer"},
        )
    return {
        "access_token": create_access_token(user.id),
        "refresh_token": create_refresh_token(user.id),
        "token_type": "bearer",
    }


@router.post("/refresh")
def refresh(payload: dict, db: Session = Depends(get_db)):
    """Exchange a refresh token for a new access token."""
    token = payload.get("refresh_token", "")
    credentials_exc = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Invalid or expired refresh token",
    )
    try:
        data = jwt.decode(token, settings.secret_key, algorithms=[ALGORITHM])
        if data.get("type") != "refresh":
            raise credentials_exc
        user_id = int(data["sub"])
    except (JWTError, KeyError, ValueError):
        raise credentials_exc

    user = db.get(models.User, user_id)
    if user is None:
        raise credentials_exc

    return {
        "access_token": create_access_token(user.id),
        "token_type": "bearer",
    }


def _user_response(user: models.User) -> dict:
    return {
        "id": user.id,
        "username": user.username,
        "sim_weight_timbre":            user.sim_weight_timbre,
        "sim_weight_timbral_variation": user.sim_weight_timbral_variation,
        "sim_weight_harmony":           user.sim_weight_harmony,
        "sim_weight_chord_movement":    user.sim_weight_chord_movement,
        "sim_weight_tempo":             user.sim_weight_tempo,
        "sim_weight_loudness":          user.sim_weight_loudness,
        "sim_weight_dynamic_range":     user.sim_weight_dynamic_range,
        "sim_weight_brightness":        user.sim_weight_brightness,
        "sim_weight_tonal":             user.sim_weight_tonal,
    }


@router.get("/me")
def me(current_user: models.User = Depends(get_current_user)):
    return _user_response(current_user)


_WEIGHT_KEYS = [
    "timbre",
    "timbral_variation",
    "harmony",
    "chord_movement",
    "tempo",
    "loudness",
    "dynamic_range",
    "brightness",
    "tonal",
]


@router.put("/similarity-weights")
def update_similarity_weights(
    body: dict,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    for key in _WEIGHT_KEYS:
        if key not in body:
            continue
        value = body[key]
        if not isinstance(value, int) or value < 0 or value > 10:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Value for '{key}' must be an integer between 0 and 10",
            )
        setattr(current_user, f"sim_weight_{key}", value)
    db.commit()
    db.refresh(current_user)
    return _user_response(current_user)


@router.post("/change-password", status_code=204)
def change_password(
    payload: dict,
    current_user: models.User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    from app.auth import hash_password
    if not verify_password(payload.get("current_password", ""), current_user.password_hash):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Current password is incorrect")
    new_password = payload.get("new_password", "")
    if len(new_password) < 8:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="New password must be at least 8 characters")
    current_user.password_hash = hash_password(new_password)
    db.commit()
