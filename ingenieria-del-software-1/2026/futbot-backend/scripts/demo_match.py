"""Partido de desarrollo con API real y movimientos simulados.

Ejecutar desde futbot-backend: python -m scripts.demo_match
Cada ejecución agrega datos nuevos sin borrar ni modificar partidas existentes.
"""
import argparse
from dataclasses import dataclass
import math
import time
import socket
from threading import Thread

import uvicorn
from uuid import uuid4

from sqlalchemy.orm import Session

from app.core.security import hash_password
from app.db.base import ahora_utc
from app.db.init_db import crear_tablas
from app.db.session import SessionLocal, engine
from app.models.behavior import Behavior
from app.models.club import Club
from app.models.enrollment import Enrollment
from app.models.match import Match
from app.models.match_player import MatchPlayer
from app.models.player import Player
from app.models.room import Room
from app.models.squad_entry import SquadEntry
from app.models.user import User
from app.schemas.match_state import MatchTick
from app.engine.state import publish_engine_tick

PASSWORD = 'FutbotDemo123!'
# Escala provisional de 100 x 60; (0, 0) es el centro.
FORMATION = [(-28, 12), (-16, 0), (-26, -15)]


@dataclass
class Demo:
    match_id: str
    room_id: str
    emails: list[str]
    club_ids: list[str]
    player_ids: list[list[str]]
    duration: int


def make_tick(demo: Demo, elapsed: int) -> MatchTick:
    players = []
    for side, ids in enumerate(demo.player_ids):
        for index, player_id in enumerate(ids):
            point = None
            if index < 3:
                x, y = FORMATION[index]
                direction = 1 if side == 0 else -1
                point = {
                    'x': round(direction * (x + 5 * math.sin(elapsed / (5 + index))), 2),
                    'y': round(direction * (y + 3 * math.sin(elapsed / (7 + index))), 2),
                }
            players.append({'player_id': player_id, 'on_field': index < 3, 'position': point})
    owner_side = (elapsed // 10) % 2
    owner = players[owner_side * 6 + 1]
    first_goal, second_goal = demo.duration // 3, 2 * demo.duration // 3
    score = {'home': int(elapsed >= first_goal), 'away': int(elapsed >= second_goal)}
    actions = []
    if elapsed in (first_goal, second_goal):
        side = 0 if elapsed == first_goal else 1
        actions.append({'type': 'goal', 'player_id': demo.player_ids[side][1], 'club_id': demo.club_ids[side]})
    elif 0 < elapsed < demo.duration:
        actions.append({'type': 'movement', 'player_id': owner['player_id'],
                        'club_id': demo.club_ids[owner_side], 'destination': owner['position']})
    return MatchTick.model_validate({
        'status': 'finished' if elapsed >= demo.duration else 'in_progress',
        'current_time': elapsed, 'score': score,
        'ball': {**owner['position'], 'owner_player_id': owner['player_id']},
        'players': players, 'actions': actions,
    })


def create_demo(db: Session, duration: int = 120) -> Demo:
    if duration < 10:
        raise ValueError('La duración mínima es de 10 segundos')
    suffix = uuid4().hex[:12]
    emails, clubs, squads = [], [], []
    password_hash = hash_password(PASSWORD)
    for side, label in enumerate(('local', 'visitante')):
        email = f'demo.{label}.{suffix}@futbot.test'
        user = User(username=f'demo-{label}-{suffix}', email=email, password_hash=password_hash)
        user.club = Club(name=f'Demo {label.title()} {suffix}')
        db.add(user)
        db.flush()
        club = user.club
        emails.append(email)
        clubs.append(club.id)
        behavior = Behavior(club_id=club.id, name='Demo sin motor',
                            code='def comportamiento(jugador):\n    pass\n', is_preprogrammed=False)
        db.add(behavior)
        db.flush()
        squad = []
        for index in range(6):
            player = Player(club_id=club.id, name=f'{label.title()} {index + 1}',
                            power=60, agility=60, control=60, speed=60, strength=60,
                            is_playing=True)
            db.add(player)
            db.flush()
            squad.append((player.id, behavior.id))
        squads.append(squad)
    now = ahora_utc()
    room = Room(type='friendly', creator_club_id=clubs[0], min_clubs=2, max_clubs=2,
                match_duration_minutes=math.ceil(duration / 60), status='in_progress', started_at=now)
    db.add(room)
    db.flush()
    match = Match(room_id=room.id, home_club_id=clubs[0], away_club_id=clubs[1],
                  duration_seconds=duration, status='in_progress', started_at=now)
    db.add(match)
    db.flush()
    for side, squad in enumerate(squads):
        db.add(Enrollment(room_id=room.id, club_id=clubs[side]))
        for index, (player_id, behavior_id) in enumerate(squad):
            starter = index < 3
            direction = 1 if side == 0 else -1
            x, y = FORMATION[index] if starter else (None, None)
            db.add(SquadEntry(room_id=room.id, player_id=player_id, behavior_id=behavior_id,
                              role='starter' if starter else 'substitute'))
            db.add(MatchPlayer(match_id=match.id, club_id=clubs[side], player_id=player_id,
                               behavior_id=behavior_id, on_field=starter,
                               initial_x=direction * x if starter else None,
                               initial_y=direction * y if starter else None))
    db.flush()
    demo = Demo(match.id, room.id, emails, clubs, [[p[0] for p in squad] for squad in squads], duration)
    db.commit()
    publish_engine_tick(db, demo.match_id, make_tick(demo, 0), expected_revision=0)
    return demo


def advance_demo(db: Session, demo: Demo, elapsed: int, revision: int) -> int:
    state = publish_engine_tick(db, demo.match_id, make_tick(demo, elapsed), expected_revision=revision)
    return state.revision


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--duration', type=int, default=120, help='Segundos simulados (mínimo 10; por defecto 120)')
    parser.add_argument('--frontend-url', default='http://localhost:5173')
    parser.add_argument('--static', action='store_true', help='Servir solo el estado inicial, sin animación')
    parser.add_argument('--port', type=int, default=8000, help='Puerto del backend de la demo')
    parser.add_argument('--no-wait', action='store_true', help='Comenzar sin esperar Enter')
    args = parser.parse_args()
    if args.duration < 10:
        parser.error('--duration debe ser al menos 10')
    # La API y el simulador deben compartir el dict de estados y el manager.
    # Reservar el puerto antes de crear datos evita demos huérfanas si está ocupado.
    listener = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    listener.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    try:
        listener.bind(('127.0.0.1', args.port))
    except OSError as error:
        listener.close()
        parser.error(f'Puerto {args.port} no disponible. Detené el otro backend o elegí --port. {error}')
    listener.listen(128)
    server = uvicorn.Server(uvicorn.Config('app.main:app', host='127.0.0.1', port=args.port,
                                         log_level='warning', timeout_graceful_shutdown=3))
    thread = Thread(target=server.run, kwargs={'sockets': [listener]}, daemon=True)
    try:
        crear_tablas(engine)
        with SessionLocal() as db:
            demo = create_demo(db, args.duration)
        thread.start()
        deadline = time.monotonic() + 30
        while not server.started:
            if not thread.is_alive() or time.monotonic() > deadline:
                raise RuntimeError('No se pudo iniciar la API de la demo')
            time.sleep(.05)
        url = args.frontend_url.rstrip('/')
        print(f'\nBackend DEMO en http://localhost:{args.port}. No hace falta otro uvicorn.')
        print('Partido DEMO creado. Los movimientos y goles son simulados.')
        print(f'Login: {url}/login')
        print(f'Usuario local: {demo.emails[0]}\nUsuario visitante: {demo.emails[1]}')
        print(f'Contraseña para ambos: {PASSWORD}')
        print(f'ID del partido: {demo.match_id}\nAbrir después del login: {url}/partidos/{demo.match_id}', flush=True)
        if args.static:
            print('Estado inicial disponible. Ctrl+C detiene la demo y su backend.', flush=True)
        else:
            if not args.no_wait:
                input('\nIniciá sesión y abrí el partido. Presioná Enter aquí para animarlo… ')
            revision = 1
            for elapsed in range(1, demo.duration + 1):
                time.sleep(1)
                with SessionLocal() as db:
                    revision = advance_demo(db, demo, elapsed, revision)
                if elapsed % 10 == 0 or elapsed == demo.duration:
                    print(f'Demo: {elapsed}/{demo.duration} segundos', flush=True)
            print('Partido finalizado 1–1; ambos goles quedaron guardados. Ctrl+C para salir.', flush=True)
        # Mantener la API para consultar el resultado final o el estado estático.
        thread.join()
    except (KeyboardInterrupt, EOFError):
        print('\nDemo detenida. Se conservan goles y resultados confirmados; el estado en vivo era temporal.')
    finally:
        server.should_exit = True
        if thread.is_alive():
            thread.join(timeout=5)
        listener.close()


if __name__ == '__main__':
    main()
