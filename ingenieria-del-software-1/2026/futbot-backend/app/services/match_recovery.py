"""Recover friendly matches whose in-memory engine was lost on shutdown."""

import logging

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.base import ahora_utc
from app.models.match import ESTADO_FINISHED, ESTADO_IN_PROGRESS, ESTADO_PAUSED, Match
from app.models.match_player import MatchPlayer
from app.models.player import Player
from app.models.room import ROOM_STATUS_CANCELLED, ROOM_TYPE_FRIENDLY, Room

logger = logging.getLogger(__name__)


def recover_interrupted_friendly_matches(db: Session) -> int:
    """Close friendly matches left active after a process restart.

    Match simulation state lives in memory, so an in-progress friendly cannot
    continue after restart. Cancel its room and release its players rather than
    leaving them permanently unavailable.
    """
    interrupted = db.scalars(
        select(Match)
        .join(Room, Room.id == Match.room_id)
        .where(
            Room.type == ROOM_TYPE_FRIENDLY,
            Match.status.in_((ESTADO_IN_PROGRESS, ESTADO_PAUSED)),
        )
    ).all()
    match_ids = [match.id for match in interrupted]
    room_ids = {match.room_id for match in interrupted}
    if interrupted:
        now = ahora_utc()
        for match in interrupted:
            match.status = ESTADO_FINISHED
            match.finished_at = now

        for room in db.scalars(select(Room).where(Room.id.in_(room_ids))):
            room.status = ROOM_STATUS_CANCELLED
            room.finished_at = now

        # Make status changes visible to the active-roster query below.
        db.flush()

    # A player may also belong to another active match. Preserve that lock.
    still_active_players = set(
        db.scalars(
            select(MatchPlayer.player_id)
            .join(Match, Match.id == MatchPlayer.match_id)
            .where(Match.status.in_((ESTADO_IN_PROGRESS, ESTADO_PAUSED)))
        )
    )
    # `is_playing` is a cached flag. Clear it wherever no active match owns
    # the player, including flags left behind by earlier interrupted runs.
    locked_player_ids = set(
        db.scalars(select(Player.id).where(Player.is_playing.is_(True)))
    )
    releasable_ids = locked_player_ids - still_active_players
    if releasable_ids:
        for player in db.scalars(select(Player).where(Player.id.in_(releasable_ids))):
            player.is_playing = False

    db.commit()
    if interrupted or releasable_ids:
        logger.warning(
            "Se cancelaron %s amistosos interrumpidos y se liberaron %s jugadores",
            len(interrupted),
            len(releasable_ids),
        )
    return len(interrupted)
