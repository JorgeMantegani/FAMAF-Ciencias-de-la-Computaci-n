import secrets

from pydantic.alias_generators import to_camel
from sqlalchemy import exists, func, select, update
from sqlalchemy.orm import Session

from app.core.security import hash_password, verify_password
from app.models.behavior import Behavior
from app.models.club import Club
from app.models.enrollment import Enrollment
from app.models.match import ESTADO_FINISHED, Match
from app.models.player import Player
from app.models.room import (
    MAX_LEAGUE_CLUBS,
    MIN_LEAGUE_CLUBS,
    ROOM_STATUS_CANCELLED,
    ROOM_STATUS_FINISHED,
    ROOM_STATUS_IN_PROGRESS,
    ROOM_STATUS_READY_TO_START,
    ROOM_STATUS_WAITING_GUEST,
    ROOM_TYPE_PRIVATE,
    ROOM_TYPE_PUBLIC,
    Room,
)
from app.models.squad_entry import ROLE_STARTER, ROLE_SUBSTITUTE, SquadEntry
from app.schemas.league import (
    CreateLeague,
    JoinLeagueRequest,
    JoinLeagueResponse,
    LeagueDetailRead,
    LeagueResponse,
    LeagueStanding,
    LeagueSquadPlayerRead,
    ListLeagueResponse,
)
from app.services.exceptions_league import (
    AlreadyInLeague,
    DuplicateLeagueName,
    InvalidLeaguePassword,
    LeagueFull,
    LeagueLimitReached,
    LeagueNotFound,
    LeagueNotOpen,
    MaxClubsBelowMin,
    MaxClubsTooHigh,
    MinClubsTooLow,
    PasswordNotAllowedOnPublicLeague,
    WrongLeaguePassword,
)
from app.services.squad_validator import validate_squad_selection

STARTED_STATUSES = (ROOM_STATUS_IN_PROGRESS, ROOM_STATUS_FINISHED)


def fold(text: str) -> str:
    """normaliza para comparar sin distinguir mayusculas"""
    return text.casefold()


def filter_by_name(leagues: list[ListLeagueResponse], name: str | None) -> list[ListLeagueResponse]:
    """Deja las ligas cuyo nombre contiene el texto, sin distinguir mayúsculas."""
    needle = fold((name or "").strip())
    if not needle:
        return list(leagues)
    return [league for league in leagues if needle in fold(league.name or "")]


class LeagueService:
    def __init__(self, db: Session):
        self.db = db

    def list_leagues(self, name: str | None = None) -> list[ListLeagueResponse]:
        # Cantidad de clubes inscriptos por sala
        counts = (
            select(Enrollment.room_id.label("room_id"), func.count(Enrollment.club_id).label("total"))
            .group_by(Enrollment.room_id)
            .subquery()
        )

        query = (
            select(Room, func.coalesce(counts.c.total, 0))
            .outerjoin(counts, counts.c.room_id == Room.id)      # una liga sin inscriptos cuenta 0
            .where(
                Room.type == ROOM_TYPE_PUBLIC,                   # solo ligas públicas (ni privadas ni amistosos)
                Room.status != ROOM_STATUS_CANCELLED,
            )
        )
        rows = list(self.db.execute(query).all())
        rows.sort(key=lambda row: (fold(row[0].name or ""), row[0].id))

        leagues = [
            ListLeagueResponse(
                id=room.id,
                name=room.name,
                participants_count=total,
                started=room.status in STARTED_STATUSES,
                is_private=False,                                # el listado solo incluye públicas
                has_penalty_shootout=room.has_penalty_shootout,
            )
            for room, total in rows
        ]
        return filter_by_name(leagues, name)


MIN_LEAGUE_PASSWORD_LENGTH = 6
MAX_LEAGUE_PASSWORD_BYTES = 72  # límite de bcrypt
CODE_GENERATION_ATTEMPTS = 10


# Crea la liga, inscribe al club creador con su escuadra y devuelve la respuesta.
# Todo se guarda en una sola transacción: si algo falla, no queda nada a medias.
def create_league(db: Session, data: CreateLeague, creator_club: Club) -> LeagueResponse:
    try:
        # Primero las validaciones que no consultan la BD, después las que sí.
        _validate_club_limits(data.min_clubs, data.max_clubs)
        _validate_privacy(data.is_private, data.password)
        _validate_unique_name(db, data.name)
        validate_squad_selection(db, creator_club.id, data.starters, data.substitutes)

        # Una liga privada guarda el hash de la contraseña; una pública, None.
        password_hash = hash_password(data.password) if data.is_private else None

        room = Room(
            name=data.name,
            type=ROOM_TYPE_PRIVATE if data.is_private else ROOM_TYPE_PUBLIC,
            password_hash=password_hash,
            min_clubs=data.min_clubs,
            max_clubs=data.max_clubs,
            match_duration_minutes=data.match_duration,
            code=_generate_unique_code(db),
            creator_club_id=creator_club.id,
            has_penalty_shootout=data.has_penalty_shootout,
        )
        db.add(room)
        # Flush para obtener room.id antes de crear el enrollment y la escuadra.
        db.flush()

        db.add(Enrollment(room_id=room.id, club_id=creator_club.id))

        squad_entries = []
        for selection in data.starters:
            squad_entries.append(
                SquadEntry(
                    room_id=room.id,
                    player_id=selection.player_id,
                    behavior_id=selection.behavior_id,
                    role=ROLE_STARTER,
                )
            )
        for selection in data.substitutes:
            squad_entries.append(
                SquadEntry(
                    room_id=room.id,
                    player_id=selection.player_id,
                    behavior_id=selection.behavior_id,
                    role=ROLE_SUBSTITUTE,
                )
            )
        db.add_all(squad_entries)
        db.flush()

        response = LeagueResponse(
            id=room.id,
            name=room.name,
            is_private=room.type == ROOM_TYPE_PRIVATE,
            has_penalty_shootout=room.has_penalty_shootout,
            started=False,
            creator_id=room.creator_club_id,
            code_to_join=room.code,
        )

        db.commit()
        return response
    # Ante cualquier error se revierte toda la transacción y se propaga.
    except Exception:
        db.rollback()
        raise


def get_league_standings(db: Session, league_id: str) -> list[LeagueStanding]:
    room = db.scalar(
        select(Room).where(
            Room.id == league_id,
            Room.type.in_((ROOM_TYPE_PUBLIC, ROOM_TYPE_PRIVATE)),
        )
    )
    if room is None:
        raise LeagueNotFound()

    club_rows = db.execute(
        select(Club).join(Enrollment, Enrollment.club_id == Club.id).where(
            Enrollment.room_id == room.id
        )
    ).scalars()
    stats = {
        club.id: {
            "club_id": club.id,
            "club_name": club.name,
            "points": 0,
            "matches_played": 0,
            "matches_won": 0,
            "matches_drawn": 0,
            "matches_lost": 0,
            "goals_for": 0,
            "goals_against": 0,
        }
        for club in club_rows
    }

    matches = db.scalars(
        select(Match).where(
            Match.room_id == room.id,
            Match.status == ESTADO_FINISHED,
        )
    )
    for match in matches:
        home = stats[match.home_club_id]
        away = stats[match.away_club_id]
        home["matches_played"] += 1
        away["matches_played"] += 1
        home["goals_for"] += match.home_goals
        home["goals_against"] += match.away_goals
        away["goals_for"] += match.away_goals
        away["goals_against"] += match.home_goals

        if match.home_goals == match.away_goals:
            penalty_winner = (
                match.penalty_winner_club_id
                if room.has_penalty_shootout
                else None
            )
            if penalty_winner == match.home_club_id:
                home["points"] += 2
                home["matches_won"] += 1
                away["matches_lost"] += 1
            elif penalty_winner == match.away_club_id:
                away["points"] += 2
                away["matches_won"] += 1
                home["matches_lost"] += 1
            else:
                home["points"] += 1
                away["points"] += 1
                home["matches_drawn"] += 1
                away["matches_drawn"] += 1
        elif match.home_goals > match.away_goals:
            home["points"] += 3
            home["matches_won"] += 1
            away["matches_lost"] += 1
        else:
            away["points"] += 3
            away["matches_won"] += 1
            home["matches_lost"] += 1

    standings = [
        LeagueStanding(
            **row,
            goal_difference=row["goals_for"] - row["goals_against"],
        )
        for row in stats.values()
    ]
    return sorted(
        standings,
        key=lambda row: (
            -row.points,
            -row.goal_difference,
            -row.goals_for,
            row.club_name.casefold(),
            row.club_id,
        ),
    )


# Falla si ya existe una liga con ese nombre (sin distinguir mayúsculas).
def _validate_unique_name(db: Session, name: str) -> None:
    room = db.scalar(select(Room).where(func.lower(Room.name) == name.lower()))
    if room is not None:
        raise DuplicateLeagueName(name)


# Falla si el mínimo o el máximo de clubes están fuera de rango o son inconsistentes.
def _validate_club_limits(min_clubs: int, max_clubs: int) -> None:
    if min_clubs < MIN_LEAGUE_CLUBS:
        raise MinClubsTooLow(min_clubs)
    if max_clubs > MAX_LEAGUE_CLUBS:
        raise MaxClubsTooHigh(max_clubs)
    if max_clubs < min_clubs:
        raise MaxClubsBelowMin(max_clubs, min_clubs)


# Genera un código hexadecimal de 8 caracteres que no exista en otra sala.
def _generate_unique_code(db: Session) -> str:
    for _ in range(CODE_GENERATION_ATTEMPTS):
        code = secrets.token_hex(4)
        if db.scalar(select(Room).where(Room.code == code)) is None:
            return code

    raise RuntimeError("Could not generate a unique code for the league.")


# Valida la combinación is_private/password, antes de hashear.
def _validate_privacy(is_private: bool, password: str | None) -> None:
    if not is_private:
        if password:
            raise PasswordNotAllowedOnPublicLeague()
        return

    if not password:
        raise InvalidLeaguePassword("a password is required for private leagues")
    if len(password) < MIN_LEAGUE_PASSWORD_LENGTH:
        raise InvalidLeaguePassword(
            f"it must have at least {MIN_LEAGUE_PASSWORD_LENGTH} characters"
        )
    if len(password.encode("utf-8")) > MAX_LEAGUE_PASSWORD_BYTES:
        raise InvalidLeaguePassword(f"it cannot exceed {MAX_LEAGUE_PASSWORD_BYTES} bytes")
    if any(char.isspace() for char in password):
        raise InvalidLeaguePassword("it cannot contain spaces")


LEAGUE_TYPES = (ROOM_TYPE_PUBLIC, ROOM_TYPE_PRIVATE)
# A league accepts clubs until it starts.
OPEN_LEAGUE_STATES = (ROOM_STATUS_WAITING_GUEST, ROOM_STATUS_READY_TO_START)
ACTIVE_LEAGUE_STATES = (*OPEN_LEAGUE_STATES, ROOM_STATUS_IN_PROGRESS)
MAX_ACTIVE_LEAGUES = 2


def join_league(
    db: Session, league_id: str, club: Club, request: JoinLeagueRequest
) -> JoinLeagueResponse:
    room = db.get(Room, league_id)
    if room is None or room.type not in LEAGUE_TYPES:
        raise LeagueNotFound()
    if room.status not in OPEN_LEAGUE_STATES:
        raise LeagueNotOpen()
    if room.type == ROOM_TYPE_PRIVATE and not verify_password(
        request.password or "", room.password_hash
    ):
        raise WrongLeaguePassword()

    try:
        _lock_open_league(db, room.id)
        _check_can_enroll(db, room, club.id)
        validate_squad_selection(db, club.id, request.starters, request.substitutes)

        enrollment = Enrollment(room_id=room.id, club_id=club.id)
        db.add(enrollment)
        for role, selections in (
            (ROLE_STARTER, request.starters),
            (ROLE_SUBSTITUTE, request.substitutes),
        ):
            db.add_all(
                SquadEntry(
                    room_id=room.id,
                    player_id=s.player_id,
                    behavior_id=s.behavior_id,
                    role=role,
                )
                for s in selections
            )
        db.flush()

        response = JoinLeagueResponse(
            enrollment_id=enrollment.id, club_id=club.id, league_id=room.id
        )
        db.commit()
        return response
    except Exception:
        db.rollback()
        raise


def _lock_open_league(db: Session, league_id: str) -> None:
    # No-op write that takes the room's write lock, so concurrent joins can't race the counts.
    locked = db.execute(
        update(Room)
        .where(Room.id == league_id, Room.status.in_(OPEN_LEAGUE_STATES))
        .values(status=Room.status)
        .execution_options(synchronize_session=False)
    ).rowcount
    if locked != 1:
        raise LeagueNotOpen()


def _check_can_enroll(db: Session, room: Room, club_id: str) -> None:
    already_enrolled = db.scalar(
        select(exists().where(Enrollment.room_id == room.id, Enrollment.club_id == club_id))
    )
    if already_enrolled:
        raise AlreadyInLeague()

    active_leagues = db.scalar(
        select(func.count())
        .select_from(Enrollment)
        .join(Room, Room.id == Enrollment.room_id)
        .where(
            Enrollment.club_id == club_id,
            Room.type.in_(LEAGUE_TYPES),
            Room.status.in_(ACTIVE_LEAGUE_STATES),
        )
    )
    if active_leagues >= MAX_ACTIVE_LEAGUES:
        raise LeagueLimitReached(MAX_ACTIVE_LEAGUES)

    enrolled_clubs = db.scalar(
        select(func.count()).select_from(Enrollment).where(Enrollment.room_id == room.id)
    )
    if enrolled_clubs >= room.max_clubs:
        raise LeagueFull()


def get_league(db: Session, league_id: str, club: Club) -> LeagueDetailRead:
    room = db.get(Room, league_id)
    if room is None or room.type not in LEAGUE_TYPES:
        raise LeagueNotFound()

    club_ids = set(db.scalars(select(Enrollment.club_id).where(Enrollment.room_id == room.id)))
    is_enrolled = club.id in club_ids
    return LeagueDetailRead(
        league_id=room.id,
        name=room.name,
        is_private=room.type == ROOM_TYPE_PRIVATE,
        status=to_camel(room.status),
        min_clubs=room.min_clubs,
        max_clubs=room.max_clubs,
        enrolled_clubs=len(club_ids),
        match_duration_minutes=room.match_duration_minutes,
        is_enrolled=is_enrolled,
        my_squad=_load_club_squad(db, room.id, club.id) if is_enrolled else None,
    )


def get_league_by_code(db: Session, code: str, club: Club) -> LeagueDetailRead:
    league_id = db.scalar(
        select(Room.id).where(Room.code == code.strip().lower(), Room.type.in_(LEAGUE_TYPES))
    )
    if league_id is None:
        raise LeagueNotFound()
    return get_league(db, league_id, club)


def _load_club_squad(db: Session, league_id: str, club_id: str) -> list[LeagueSquadPlayerRead]:
    rows = db.execute(
        select(SquadEntry.role, Player.id, Player.name, Behavior.id, Behavior.name)
        .join(Player, SquadEntry.player_id == Player.id)
        .join(Behavior, SquadEntry.behavior_id == Behavior.id)
        .where(SquadEntry.room_id == league_id, Player.club_id == club_id)
    ).all()
    squad = [
        LeagueSquadPlayerRead(
            player_id=player_id,
            name=player_name,
            role=role,
            behavior_id=behavior_id,
            behavior_name=behavior_name,
        )
        for role, player_id, player_name, behavior_id, behavior_name in rows
    ]
    # Starters first.
    squad.sort(key=lambda p: p.role != ROLE_STARTER)
    return squad
