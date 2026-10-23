from sqlalchemy.orm import Session
from sqlalchemy import or_
from app.models.behavior import Behavior

def get_all_behavior(db: Session, club_id: str):
    return db.query(Behavior).filter(
        or_(
            Behavior.club_id == club_id,
            Behavior.club_id == None
        )
    ).all()

