import asyncio
from app.engine.field import FieldConfig
from sqlalchemy.orm import Session
from sqlalchemy import or_
from app.engine.match_engine import MatchPhase, MatchEngine
from app.core.config import get_settings
from app.engine.setup import PlayerSpec, create_initial_state
from app.behaviors.loader import compile_and_cache_behavior
from app.models.player import Player
from app.models.behavior import Behavior


async def run_simulation(
    db:Session,
    player_id: str,
    behavior_id: str,
    club_id: str,
    send_tick_callback # funcion para mandar mensaje por ws
):
  # Valida que el jugador y comportamiento sean del club
  player, behavior = get_simulation_resources(db, player_id, behavior_id, club_id)

  if not player or not behavior:
    raise ValueError("Jugador o comportamiento no encontrado o no pertenecen al club")

  compile_and_cache_behavior(behavior_id, behavior.code)

  # Creo playerSpec para el jugador
  player_spec = PlayerSpec(
    id=player.id,
    speed=player.speed,
    control=player.control,
    strength=player.strength,
    power=player.power,
    agility=player.agility
  )

  static_rivals = []
  static_teammate = []
  # Creo 3 rivales estatico por ahora
  for i in range(3):
    rival = PlayerSpec(
      id=f"static_rival_{i}",
      speed=60, control=60,strength=60,power=60,agility=60
    )
    static_rivals.append(rival)
  # Creo 2 compañeros estaticos por ahora
  for i in range(2):
    teammate = PlayerSpec(
      id=f"static_teammate_{i}",
      speed=60, control=60,strength=60,power=60,agility=60
    )
    static_teammate.append(teammate)
  
  field = FieldConfig()
  state = create_initial_state(
    field=field,
    home=[player_spec] + static_teammate,
    away=static_rivals,
    is_simulation_mode=True
  )
  defense = get_default_behavior(db, "defense")
  goalkeeper = get_default_behavior(db, "goalkeeper")
  behavior_ids = {
    player.id: behavior_id,
    static_rivals[0].id: goalkeeper.id,
    static_rivals[1].id: defense.id,
    static_rivals[2].id: defense.id,
    static_teammate[0].id: defense.id,
    static_teammate[1].id: defense.id,
  }
  
  engine = MatchEngine(
    state=state, 
    field=field, 
    cfg=get_settings(),
    behavior_ids=behavior_ids,
    controllable_player_ids=set(behavior_ids),
  )

  try:
    # Ejecuta la simulación durante 30 segundos o hasta que se complete
    max_ticks = 30 * get_settings().match_tick_rate

    ticks = 0
    engine.start()
    while ticks < max_ticks and engine.state.phase != MatchPhase.FINISHED:
      await engine.tick()
      snapshot = _serialize_tick(engine.state)
      await send_tick_callback(snapshot)
      ticks += 1
      await asyncio.sleep(engine.dt)
  finally:
    engine.close()

def _serialize_tick(state):
  return {
    "type": "tick",
    "players": [
      {
        "id": player.id,
        "position": {
          "x": player.pos.x,
          "y": player.pos.y
        },
        "team": player.team.name,
        "attributes": {
          "speed": player.speed,
          "control": player.control,
          "strength": player.strength,
          "power": player.power,
          "agility": player.agility
        }
      }
      for player in state.players
    ],
    "ball": {
      "position": {
        "x": state.ball.pos.x,
        "y": state.ball.pos.y
      },
      "owner_id": state.ball.owner_id,
      "velocity": {
        "x": state.ball.vel.x,
        "y": state.ball.vel.y
      }
    }
  }

def get_simulation_resources(db, player_id, behavior_id, club_id) -> tuple[Player, Behavior]:
  """
  Devuelva jugador y comportamiento, o lance un error controlado.
  """
  player = db.query(Player).filter(
    Player.id == player_id,
    Player.club_id == club_id,
    Player.deleted_at.is_(None),
  ).first()
  behavior = db.query(Behavior).filter(
    Behavior.id == behavior_id,
    or_(
      Behavior.club_id == club_id,
      Behavior.club_id.is_(None)
      ),  # permite comportamientos preprogramados
    Behavior.deleted_at.is_(None),
  ).first()

  if player is None:
      raise ValueError("Jugador no encontrado o no pertenece al club")

  if behavior is None:
      raise ValueError(
          "Comportamiento no encontrado o no pertenece al club"
      )
  return player, behavior

def get_default_behavior(db: Session, name: str) -> Behavior:
  """
  Asigna comportamientos por defecto a jugadores que no tengan uno asignado.
  """
  behavior_default = db.query(Behavior).filter(
    Behavior.name == name,
    Behavior.is_preprogrammed.is_(True),
    Behavior.deleted_at.is_(None),
  ).one()
  return behavior_default

