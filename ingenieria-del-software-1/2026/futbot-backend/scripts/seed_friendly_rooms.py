"""Seeds two test clubs and two friendly rooms for manual testing.

Usage, from the backend root:  .venv\\Scripts\\python.exe -m scripts.seed_friendly_rooms
Only adds data. Re-runnable: reuses the test users, creates new players and rooms each time.
"""
import random
import string

from sqlalchemy import select
from sqlalchemy.orm import Session

import app.models  # noqa: F401
from app.core.security import hash_password
from app.db.base import Base
from app.db.init_db import cargar_comportamientos_por_defecto
from app.db.session import engine
from app.models.behavior import Behavior
from app.models.club import Club
from app.models.enrollment import Enrollment
from app.models.player import Player
from app.models.room import (
    ROOM_STATUS_READY_TO_START,
    ROOM_STATUS_WAITING_GUEST,
    ROOM_TYPE_FRIENDLY,
    Room,
)
from app.models.squad_entry import ROLE_STARTER, ROLE_SUBSTITUTE, SquadEntry
from app.models.user import User

PASSWORD = "Futbot1234"
FRONTEND_URL = "http://localhost:5173"

HOME = {
    "email": "local@futbot.test",
    "username": "local_futbot",
    "club_name": "Los Transistores FC",
    "players": ["Tomás Arce", "Lucía Ferro", "Bruno Paz", "Mora Quiroga", "Iván Soler", "Sofía Díaz"],
}
AWAY = {
    "email": "visitante@futbot.test",
    "username": "visitante_futbot",
    "club_name": "Club Norte",
    "players": ["Julián Mena", "Ana Ibarra", "Nico Vera", "Paula Gil", "Dante Roca", "Leo Funes"],
}
# Behavior of each player, by squad position (3 starters, then 3 substitutes).
LINEUP = ["goalkeeper", "defense", "front", "defense", "front", "goalkeeper"]


def _get_or_create_club(db: Session, data: dict) -> Club:
    user = db.scalar(select(User).where(User.email == data["email"]))
    if user is None:
        user = User(
            username=data["username"],
            email=data["email"],
            password_hash=hash_password(PASSWORD),
        )
        db.add(user)
        db.flush()
        db.add(Club(user_id=user.id, name=data["club_name"]))
        db.flush()
    return user.club


def _new_room_code(db: Session) -> str:
    while True:
        code = "".join(random.choices(string.ascii_uppercase + string.digits, k=6))
        if db.scalar(select(Room).where(Room.code == code)) is None:
            return code


def _create_room(db: Session, creator: Club, status: str) -> Room:
    room = Room(
        type=ROOM_TYPE_FRIENDLY,
        creator_club_id=creator.id,
        min_clubs=2,
        max_clubs=2,
        match_duration_minutes=5,
        status=status,
        code=_new_room_code(db),
    )
    db.add(room)
    db.flush()
    return room


def _enroll(db: Session, room: Room, club: Club, names: list[str], behaviors: dict[str, Behavior]) -> None:
    # New players every run: once a match starts, its players stay locked.
    db.add(Enrollment(room_id=room.id, club_id=club.id))
    for index, name in enumerate(names):
        player = Player(
            club_id=club.id, name=name, power=60, agility=60, control=60, speed=60, strength=60
        )
        db.add(player)
        db.flush()
        db.add(
            SquadEntry(
                room_id=room.id,
                player_id=player.id,
                behavior_id=behaviors[LINEUP[index]].id,
                role=ROLE_STARTER if index < 3 else ROLE_SUBSTITUTE,
            )
        )


def seed(db: Session) -> dict[str, Room]:
    """Creates a room ready to start and one waiting for a guest; returns them."""
    cargar_comportamientos_por_defecto(db)
    behaviors = {
        b.name: b for b in db.scalars(select(Behavior).where(Behavior.club_id.is_(None)))
    }
    missing = set(LINEUP) - set(behaviors)
    if missing:
        raise RuntimeError(f"Faltan los comportamientos por defecto: {sorted(missing)}")

    home = _get_or_create_club(db, HOME)
    away = _get_or_create_club(db, AWAY)

    ready = _create_room(db, home, ROOM_STATUS_READY_TO_START)
    _enroll(db, ready, home, HOME["players"], behaviors)
    _enroll(db, ready, away, AWAY["players"], behaviors)

    waiting = _create_room(db, home, ROOM_STATUS_WAITING_GUEST)
    _enroll(db, waiting, home, HOME["players"], behaviors)

    db.commit()
    return {"ready": ready, "waiting": waiting}


def main() -> None:
    Base.metadata.create_all(engine)
    with Session(engine) as db:
        rooms = seed(db)
        print(f"Usuarios de prueba (contraseña: {PASSWORD}):")
        print(f"  Local:     {HOME['email']}  ({HOME['club_name']})")
        print(f"  Visitante: {AWAY['email']}  ({AWAY['club_name']})")
        print(f"Sala lista para iniciar: {FRONTEND_URL}/amistosos/{rooms['ready'].id}/sala")
        print(f"Sala esperando rival:    {FRONTEND_URL}/amistosos/{rooms['waiting'].id}/sala")


if __name__ == "__main__":
    main()
