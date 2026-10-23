from collections import Counter

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


def _invalid_squad() -> HTTPException:
    return _error(
        status.HTTP_400_BAD_REQUEST,
        "INVALID_SQUAD",
        "Algún club no tiene sus 3 titulares y 3 suplentes con comportamientos válidos",
    )


def _validate_squads(
    db: Session,
    rows: list[tuple[SquadEntry, Player, Behavior]],
    club_ids: set[str],
) -> None:
    """Each club needs 3 starters and 3 substitutes with usable players and behaviors."""
    roles_per_club: dict[str, Counter] = {club_id: Counter() for club_id in club_ids}
    player_ids = {player.id for _, player, _ in rows}
    active_player_ids = set(
        db.scalars(
            select(MatchPlayer.player_id)
            .join(Match, Match.id == MatchPlayer.match_id)
            .where(
                MatchPlayer.player_id.in_(player_ids),
                Match.status.in_(ACTIVE_MATCH_STATES),
            )
        )
    )

    for entry, player, behavior in rows:
        if player.club_id not in club_ids:
            print("este es el problema")
            raise _invalid_squad()
        if player.deleted_at is not None or player.id in active_player_ids:
            raise _invalid_squad()
        # is_playing is a cached flag. Clear stale values left by finished
        # matches, while active match membership remains authoritative.
        if player.is_playing:
            player.is_playing = False
        if behavior.deleted_at is not None or behavior.club_id not in (
            None,
            player.club_id,
        ):
            raise _invalid_squad()
        roles_per_club[player.club_id][entry.role] += 1

    expected = Counter({ROLE_STARTER: STARTER_COUNT, ROLE_SUBSTITUTE: SUBSTITUTE_COUNT})
    if any(roles != expected for roles in roles_per_club.values()):
        raise _invalid_squad()


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
        room_code=room.code,
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
    _validate_squads(db, rows, club_ids)

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
