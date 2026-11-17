from fastapi import HTTPException, status
from sqlalchemy import exists, select, update
from sqlalchemy.exc import IntegrityError
from pydantic.alias_generators import to_camel
from sqlalchemy.orm import Session

from app.db.base import ahora_utc as utc_now
from app.models.behavior import Behavior
from app.models.club import Club
from app.models.enrollment import Enrollment
from app.models.match import (
    ESTADO_IN_PROGRESS as MATCH_IN_PROGRESS,
    ESTADO_PAUSED as MATCH_PAUSED,
    ESTADO_PRE_MATCH as MATCH_PRE_MATCH,
    Match,
)
from app.models.match_player import MatchPlayer
from app.models.player import Player
from app.models.room import (
    ROOM_STATUS_FINISHED,
    ROOM_STATUS_IN_PROGRESS,
    ROOM_STATUS_READY_TO_START,
    ROOM_TYPE_FRIENDLY,
    Room,
)
from app.models.squad_entry import (
    ROLE_STARTER,
    ROLE_SUBSTITUTE,
    STARTER_COUNT,
    SUBSTITUTE_COUNT,
    SquadEntry,
)
from app.schemas.friendly_room import (
    FriendlyRoomClubRead,
    FriendlyRoomPlayerRead,
    FriendlyRoomRead,
)
from app.services.squad_validator import validate_squad_selection

"""Business logic for friendly rooms."""

FRIENDLY_CLUBS = 2
STARTED_ROOM_STATES = (ROOM_STATUS_IN_PROGRESS, ROOM_STATUS_FINISHED)
ACTIVE_MATCH_STATES = (MATCH_PRE_MATCH, MATCH_IN_PROGRESS, MATCH_PAUSED)


def _error(status_code: int, error_code: str, message: str) -> HTTPException:
    return HTTPException(
        status_code=status_code,
        detail={"detail": message, "error_code": error_code},
    )


def _already_started() -> HTTPException:
    return _error(
        status.HTTP_400_BAD_REQUEST,
        "MATCH_ALREADY_STARTED",
        "El partido de esta sala ya fue iniciado",
    )


def _invalid_stored_squad(is_own: bool) -> HTTPException:
    owner = "Tu plantilla" if is_own else "La plantilla del club rival"
    return _error(
        status.HTTP_400_BAD_REQUEST,
        "INVALID_SQUAD",
        f"{owner} no tiene {STARTER_COUNT} titulares y {SUBSTITUTE_COUNT} suplentes "
        "con jugadores y comportamientos válidos",
    )


def _get_room_for_member(db: Session, room_id: str, club: Club) -> tuple[Room, set[str]]:
    """Returns the friendly room and its club ids, or 404/403."""
    room = db.get(Room, room_id)
    if room is None or room.type != ROOM_TYPE_FRIENDLY:
        raise _error(
            status.HTTP_404_NOT_FOUND, "ROOM_NOT_FOUND", "La sala amistosa no existe"
        )

    club_ids = set(
        db.scalars(select(Enrollment.club_id).where(Enrollment.room_id == room.id))
    )
    if club.id not in club_ids:
        raise _error(
            status.HTTP_403_FORBIDDEN,
            "NOT_ROOM_MEMBER",
            "Tu club no pertenece a esta sala",
        )
    return room, club_ids


def _load_squads(db: Session, room_id: str) -> list[tuple[SquadEntry, Player, Behavior]]:
    return db.execute(
        select(SquadEntry, Player, Behavior)
        .join(Player, SquadEntry.player_id == Player.id)
        .join(Behavior, SquadEntry.behavior_id == Behavior.id)
        .where(SquadEntry.room_id == room_id)
    ).tuples().all()


def get_friendly_room(db: Session, room_id: str, club: Club) -> FriendlyRoomRead:
    room, club_ids = _get_room_for_member(db, room_id, club)
    clubs = {
        c.id: c
        for c in db.scalars(select(Club).where(Club.id.in_(club_ids | {room.creator_club_id})))
    }
    rows = _load_squads(db, room.id)
    match_id = db.scalar(select(Match.id).where(Match.room_id == room.id))

    def club_read(club_id: str) -> FriendlyRoomClubRead:
        players = [
            FriendlyRoomPlayerRead(
                player_id=player.id,
                name=player.name,
                role=entry.role,
                behavior_id=behavior.id,
                behavior_name=behavior.name,
            )
            for entry, player, behavior in rows
            if player.club_id == club_id
        ]
        # Starters first.
        players.sort(key=lambda p: p.role != ROLE_STARTER)
        return FriendlyRoomClubRead(
            club_id=club_id, club_name=clubs[club_id].name, players=players
        )

    away_ids = club_ids - {room.creator_club_id}
    return FriendlyRoomRead(
        room_id=room.id,
        status=to_camel(room.status),
        match_id=match_id,
        home_club=club_read(room.creator_club_id),
        away_club=club_read(next(iter(away_ids))) if away_ids else None,
    )


def start_friendly_match(db: Session, room_id: str, club: Club) -> Match:
    room, club_ids = _get_room_for_member(db, room_id, club)

    if room.status in STARTED_ROOM_STATES:
        raise _already_started()

    if len(club_ids) != FRIENDLY_CLUBS or room.creator_club_id not in club_ids:
        raise _error(
            status.HTTP_400_BAD_REQUEST,
            "ROOM_NOT_FULL",
            "La sala todavía no tiene club local y visitante",
        )

    if room.status != ROOM_STATUS_READY_TO_START:
        raise _error(
            status.HTTP_400_BAD_REQUEST,
            "ROOM_NOT_READY",
            "La sala no está lista para iniciar el partido",
        )

    rows = _load_squads(db, room.id)
    # SquadEntry no guarda club_id: cada entrada pertenece al club de su jugador.
    for club_id in club_ids:
        entries = [entry for entry, player, _behavior in rows if player.club_id == club_id]
        try:
            validate_squad_selection(
                db,
                club_id,
                [entry for entry in entries if entry.role == ROLE_STARTER],
                [entry for entry in entries if entry.role == ROLE_SUBSTITUTE],
            )
        except HTTPException:
            # El validador le habla a quien elige; acá la plantilla puede ser del otro club.
            raise _invalid_stored_squad(is_own=club_id == club.id) from None

    home_club_id = room.creator_club_id
    (away_club_id,) = club_ids - {home_club_id}
    now = utc_now()

    # Conditional update: if both clubs start at once, only one request wins.
    result = db.execute(
        update(Room)
        .where(Room.id == room.id, Room.status == ROOM_STATUS_READY_TO_START)
        .values(status=ROOM_STATUS_IN_PROGRESS, started_at=now)
    )
    if result.rowcount != 1:
        db.rollback()
        raise _already_started()

    match = Match(
        room_id=room.id,
        home_club_id=home_club_id,
        away_club_id=away_club_id,
        status=MATCH_IN_PROGRESS,
        duration_seconds=room.match_duration_minutes * 60,
        started_at=now,
    )
    db.add(match)
    db.flush()

    for entry, player, _behavior in rows:
        db.add(
            MatchPlayer(
                match_id=match.id,
                club_id=player.club_id,
                player_id=player.id,
                behavior_id=entry.behavior_id,
                on_field=entry.role == ROLE_STARTER,
            )
        )
        player.is_playing = True

    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise _already_started()

    return match


def is_behavior_in_active_match(db: Session, behavior_id: str) -> bool:
    return db.scalar(
        select(
            exists()
            .where(MatchPlayer.behavior_id == behavior_id)
            .where(MatchPlayer.match_id == Match.id)
            .where(Match.status.in_(ACTIVE_MATCH_STATES))
        )
    )
