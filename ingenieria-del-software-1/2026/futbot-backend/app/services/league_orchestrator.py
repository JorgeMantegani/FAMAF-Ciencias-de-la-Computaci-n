import asyncio
import uuid
from sqlalchemy import select
from sqlalchemy.orm import Session, sessionmaker
from app.models.room import Room, ROOM_STATUS_IN_PROGRESS, ROOM_STATUS_FINISHED
from app.models.match import Match, ESTADO_SCHEDULED, ESTADO_PRE_MATCH, ESTADO_IN_PROGRESS, ESTADO_FINISHED
from app.models.enrollment import Enrollment
from app.models.club import Club
from app.models.player import Player
from app.models.match_player import MatchPlayer
from app.models.squad_entry import SquadEntry, ROLE_STARTER
from app.services.match_runner import start_match
from app.services.league_ranking import settle_league_ranking
from app.core.config import get_settings
from app.ws.manager import league_manager

import uuid
from app.models.match_player import MatchPlayer
from app.models.squad_entry import SquadEntry, ROLE_STARTER
from app.models.player import Player

def ensure_match_players(db: Session, match: Match):
    """Crea los registros en MatchPlayer a partir de los SquadEntry de la liga para ambos clubes."""
    existing = db.execute(select(MatchPlayer).where(MatchPlayer.match_id == match.id)).first()
    if existing:
        return

    league_id = match.room_id

    for club_id in [match.home_club_id, match.away_club_id]:
        entries = db.execute(
            select(SquadEntry)
            .join(Player, Player.id == SquadEntry.player_id)
            .where(
                SquadEntry.room_id == league_id,
                Player.club_id == club_id
            )
        ).scalars().all()

        for entry in entries:
            is_starter = (entry.role == ROLE_STARTER)
            mp = MatchPlayer(
                id=str(uuid.uuid4()),
                match_id=match.id,
                player_id=entry.player_id,
                club_id=club_id,
                behavior_id=entry.behavior_id,
                on_field=is_starter,
                initial_x=None,
                initial_y=None,
                goals=0
            )
            db.add(mp)
    db.commit()

def get_league_lobby_payload(db: Session, league_id: str, club_id: str | None = None) -> dict:
    """Calcula y consolida el estado completo de liga activa."""
    room = db.get(Room, league_id)
    if not room or room.status not in [ROOM_STATUS_IN_PROGRESS, ROOM_STATUS_FINISHED]:
        return None

    def get_club_name(club_id):
        c = db.get(Club, club_id)
        return c.name if c else "Desconocido"

    # Partido en curso o en preparación (pre-match)
    current_match = db.execute(
        select(Match).where(
            Match.room_id == league_id, 
            Match.status.in_([ESTADO_IN_PROGRESS, ESTADO_PRE_MATCH])
        ).limit(1)
    ).scalar_one_or_none()

    next_match = db.execute(
        select(Match)
        .where(Match.room_id == league_id, Match.status == ESTADO_SCHEDULED)
        .order_by(Match.round.asc(), Match.id.asc())
        .limit(1)
    ).scalar_one_or_none()

    matches = db.execute(
        select(Match).where(Match.room_id == league_id).order_by(Match.round.asc())
    ).scalars().all()

    enrollments = db.execute(
        select(Enrollment).where(Enrollment.room_id == league_id)
    ).scalars().all()

    standing_data = []
    for enr in enrollments:
        club = db.get(Club, enr.club_id)
        goal_diff = enr.goals_for - enr.goals_against
        standing_data.append({
            "club_id": enr.club_id,
            "club_name": club.name if club else "Desconocido",
            "matches_played": enr.matches_played,
            "matches_won": enr.matches_won,
            "matches_drawn": enr.matches_drawn,
            "matches_lost": enr.matches_lost,
            "goals_for": enr.goals_for,
            "goals_against": enr.goals_against,
            "goal_difference": goal_diff,
            "points": enr.points,
        })

    sorted_standings = sorted(
        standing_data,
        key=lambda x: (
            -x["points"],
            -x["matches_won"],
            -x["goal_difference"],
            -x["goals_for"],
            x["club_name"].lower()
        )
    )
    # Info adicional, como la alineación del club del usuario
    my_squad = []

    if club_id is not None:
        my_squad = [
            {
                "player_id": entry.player_id,
                "name": player.name,
                "role": entry.role,
            }
            for entry, player in db.execute(
                select(SquadEntry, Player)
                .join(Player, Player.id == SquadEntry.player_id)
                .where(
                    SquadEntry.room_id == league_id,
                    Player.club_id == club_id,
                    Player.deleted_at.is_(None),
                )
                .order_by(SquadEntry.role, SquadEntry.player_id)
            ).all()
        ]

    return {
        "type": "league_lobby_update",
        "league_id": room.id,
        "league_name": room.name,
        "status": room.status,
        "my_squad": my_squad,
        "currentMatch": {
            "id": current_match.id,
            "home_club_id": current_match.home_club_id,
            "away_club_id": current_match.away_club_id,
            "home_club_name": get_club_name(current_match.home_club_id),
            "away_club_name": get_club_name(current_match.away_club_id),
            "home_score": current_match.home_goals,
            "away_score": current_match.away_goals,
            "round": current_match.round,
            "status": current_match.status,
        } if current_match else None,
        "nextMatch": {
            "id": next_match.id,
            "home_club_id": next_match.home_club_id,
            "away_club_id": next_match.away_club_id,
            "home_club_name": get_club_name(next_match.home_club_id),
            "away_club_name": get_club_name(next_match.away_club_id),
            "round": next_match.round,
            "status": next_match.status,
        } if next_match else None,
        "standings": sorted_standings,
        "calendar": [
            {
                "id": m.id,
                "round": m.round,
                "home_club_id": m.home_club_id,
                "away_club_id": m.away_club_id,
                "home_club_name": get_club_name(m.home_club_id),
                "away_club_name": get_club_name(m.away_club_id),
                "home_score": m.home_goals,
                "away_score": m.away_goals,
                "status": m.status,
            } for m in matches
        ],
    }


async def on_match_finished_notifier(match_id: str, data: dict, bind):
    """Callback invocado por el motor de partido al finalizar un encuentro."""
    if data.get("type") == "MATCH_FINISHED":
        league_id = None
        with Session(bind) as db:
            match = db.get(Match, match_id)
            if not match or not match.room_id:
                return
            league_id = match.room_id

            # Actualizar estadísticas en Enrollment
            home_enr = db.execute(
                select(Enrollment).where(Enrollment.room_id == league_id, Enrollment.club_id == match.home_club_id)
            ).scalar_one_or_none()

            away_enr = db.execute(
                select(Enrollment).where(Enrollment.room_id == league_id, Enrollment.club_id == match.away_club_id)
            ).scalar_one_or_none()

            if home_enr and away_enr:
                home_goals = data.get("home_goals", 0)
                away_goals = data.get("away_goals", 0)

                match.home_goals = home_goals
                match.away_goals = away_goals
                match.status = ESTADO_FINISHED

                home_enr.matches_played += 1
                away_enr.matches_played += 1
                home_enr.goals_for += home_goals
                home_enr.goals_against += away_goals
                away_enr.goals_for += away_goals
                away_enr.goals_against += home_goals

                if home_goals > away_goals:
                    home_enr.matches_won += 1
                    home_enr.points += 3
                    away_enr.matches_lost += 1
                elif home_goals < away_goals:
                    away_enr.matches_won += 1
                    away_enr.points += 3
                    home_enr.matches_lost += 1
                else:
                    home_enr.matches_drawn += 1
                    home_enr.points += 1
                    away_enr.matches_drawn += 1
                    away_enr.points += 1

                db.commit()

        # Difusión en tiempo real con una nueva sesión abierta
        if league_id:
            with Session(bind) as db_broadcast:
                updated_payload = get_league_lobby_payload(db_broadcast, league_id)
                if updated_payload:
                    await league_manager.broadcast_active(league_id, updated_payload)

            # Disparar el siguiente partido del fixture de forma automática
            asyncio.create_task(run_next_league_match(bind, league_id))


async def run_next_league_match(bind, league_id: str):
    """Busca y ejecuta el siguiente partido programado."""
    await asyncio.sleep(2)

    with Session(bind) as db:
        next_match = db.execute(
            select(Match)
            .where(Match.room_id == league_id, Match.status.in_([ESTADO_SCHEDULED, ESTADO_PRE_MATCH]))
            .order_by(Match.round.asc(), Match.id.asc())
            .limit(1)
        ).scalar_one_or_none()

        if not next_match:
            if settle_league_ranking(db, league_id):
                db.commit()
                payload = get_league_lobby_payload(db, league_id)
                if payload:
                    await league_manager.broadcast_active(league_id, payload)
            return

        # Sincronizar las alineaciones (SquadEntry) con los jugadores reales del partido (MatchPlayer)
        ensure_match_players(db, next_match)

        next_match.status = ESTADO_PRE_MATCH
        db.commit()

        # Notificar inicio de nuevo partido a los observadores
        payload = get_league_lobby_payload(db, league_id)
        if payload:
            await league_manager.broadcast_active(league_id, payload)

        # Iniciar motor de partido
        start_match(
            db, 
            next_match.id, 
            get_settings(), 
            notifier=lambda m_id, data: on_match_finished_notifier(m_id, data, bind)
        )

def generate_league_fixture(db: Session, league_id: str):
    """Genera automáticamente el fixture de todos contra todos (round-robin) para la liga."""
    enrollments = db.execute(select(Enrollment).where(Enrollment.room_id == league_id)).scalars().all()
    club_ids = [e.club_id for e in enrollments]
    if len(club_ids) < 2:
        return

    # Verificar si ya existen partidos creados
    existing_matches = db.execute(select(Match).where(Match.room_id == league_id)).scalars().all()
    if existing_matches:
        return

    import uuid
    room = db.get(Room, league_id)
    duration = (room.match_duration_minutes or 5) * 60

    teams = list(club_ids)
    if len(teams) % 2 != 0:
        teams.append(None)  # Manejo de equipo libre (bye) si la cantidad es impar

    n = len(teams)
    rounds = n - 1
    match_round = 1

    for r in range(rounds):
        for i in range(n // 2):
            home = teams[i]
            away = teams[n - 1 - i]
            if home is not None and away is not None:
                if r % 2 == 1 and i == 0:
                    home, away = away, home
                
                match = Match(
                    id=str(uuid.uuid4()),
                    room_id=league_id,
                    round=match_round,
                    home_club_id=home,
                    away_club_id=away,
                    status=ESTADO_SCHEDULED,
                    duration_seconds=duration,
                    home_goals=0,
                    away_goals=0
                )
                db.add(match)
        match_round += 1
        # Rotación de equipos para el algoritmo round-robin
        teams = [teams[0]] + [teams[-1]] + teams[1:-1]

    db.commit()
