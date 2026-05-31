from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from uuid import UUID
from typing import Optional

from app.core.database import get_db
from app.models.models import User
from app.schemas.schemas import UserCreate, UserResponse, UserPreferences

router = APIRouter(prefix="/user", tags=["user"])


@router.post("/", response_model=UserResponse)
async def create_user(user: UserCreate, db: Session = Depends(get_db)):
    """
    Create a new user or get existing user.
    """
    db_user = User(nickname=user.nickname, preferences={})
    db.add(db_user)
    db.commit()
    db.refresh(db_user)
    return db_user


@router.get("/{user_id}", response_model=UserResponse)
async def get_user(user_id: UUID, db: Session = Depends(get_db)):
    """
    Get user by ID.
    """
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    return user


@router.put("/{user_id}/preferences", response_model=UserResponse)
async def update_user_preferences(
    user_id: UUID,
    preferences: UserPreferences,
    db: Session = Depends(get_db),
):
    """
    Update user preferences.
    """
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    user.preferences = preferences.model_dump()
    db.commit()
    db.refresh(user)
    return user


@router.get("/{user_id}/stats")
async def get_user_stats(user_id: UUID, db: Session = Depends(get_db)):
    """
    Get user healing statistics.
    """
    from app.models.models import HealingSession

    sessions = db.query(HealingSession).filter(
        HealingSession.user_id == user_id
    ).all()

    total_minutes = sum(s.duration_minutes for s in sessions)
    avg_score = (
        sum(s.healing_score or 0 for s in sessions) / len(sessions)
        if sessions
        else 0
    )

    return {
        "total_sessions": len(sessions),
        "total_minutes": total_minutes,
        "average_healing_score": round(avg_score, 1),
    }