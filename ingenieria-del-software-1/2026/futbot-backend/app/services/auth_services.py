from sqlalchemy.exc import IntegrityError
from fastapi import HTTPException, status
from sqlalchemy import or_, select
from sqlalchemy.orm import Session

from app.models.user import User
from app.models.club import Club
from app.schemas.auth import UserRegister
from app.core.security import hash_password

def create_user_with_club(db: Session, user_data: UserRegister) -> User:
    hashed_password = hash_password(user_data.password)
    existing_user = db.scalar(
            select(User).where(
                or_(
                    User.username == user_data.username,
                    User.email == user_data.email,
                )
            )
        )
    existing_club = db.scalar(
            select(Club).where(Club.name == user_data.club_name)
        )
    
    if existing_user is not None or existing_club is not None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="El usuario, email o nombre del club ya existe",
        )
    
    user = User(
        username=user_data.username,
        email=user_data.email,
        password_hash=hashed_password,
    )
    db.add(user)
    
    try:
        db.flush()
        club = Club(
            name=user_data.club_name,
            avatar_url=user_data.avatar_url or "1",
            ranking_points=0,
            user_id=user.id,
        )
        db.add(club)
        db.commit()
        db.refresh(user)
    except IntegrityError:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="El usuario, email o nombre del club ya existe",
        )
    return user