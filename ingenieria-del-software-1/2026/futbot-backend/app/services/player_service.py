from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.player import Player
from app.schemas.player import PlayerCreate
from app.services.exceptions_player import (
    AttributeOutOfRange,
    DuplicatePlayerName,
    InvalidAttributeSum,
)


# Ticket: BE [BE] Endpoint Crear Jugador de Club
def create_player(db: Session, club_id: str, player_data: PlayerCreate) -> Player:
    # Business rules validated here (not left to the DB constraint) so we
    # control the HTTP status code and can unit test without a real DB.
    attributes = {
        "power": player_data.power,
        "agility": player_data.agility,
        "control": player_data.control,
        "speed": player_data.speed,
        "strength": player_data.strength,
    }

    for name, value in attributes.items():
        if value < 20 or value > 100:
            raise AttributeOutOfRange(name, value)

    total = sum(attributes.values())
    if total != 300:
        raise InvalidAttributeSum(total)

    # Enforce unique player name per club (soft-deleted players don't count).
    existing_player = db.scalar(
        select(Player).where(
            Player.club_id == club_id,
            Player.name == player_data.name,
            Player.deleted_at.is_(None),
        )
    )
    if existing_player is not None:
        raise DuplicatePlayerName(player_data.name)

    player = Player(
        club_id=club_id,
        name=player_data.name,
        power=player_data.power,
        agility=player_data.agility,
        control=player_data.control,
        speed=player_data.speed,
        strength=player_data.strength,
    )
    db.add(player)
    db.commit()
    db.refresh(player)  # pulls DB-generated fields (id, created_at)
    return player

def get_all_players(db: Session, club_id: str):
    return db.query(Player).filter(Player.club_id == club_id).all()