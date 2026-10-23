from collections.abc import Callable

import pytest

from app.behaviors import executor, loader
from app.behaviors.api import JugadorAPI
from app.behaviors.errors import ComportamientoNoEncontrado
from app.models.behavior import Behavior
from app.schemas.coord import Coord


class MotorDePrueba:
    """Motor minimo que registra las consultas y acciones del comportamiento."""

    def __init__(self, behavior_id: str = "behavior-asignado") -> None:
        self.behavior_id = behavior_id
        self.actions: list[tuple[str, str, Coord]] = []
        self.errors: list[tuple[str, str]] = []
        self.finished = False
        self.position = Coord(x=1, y=2)
        self.ball = Coord(x=3, y=4)
        self.inside_field = True
        self.has_ball = True
        self.on_field = True

    def ball_position(self):
        return self.ball

    def nearest_teammate_position(self, player_id):
        return Coord(x=5, y=6)

    def nearest_opponent_position(self, player_id):
        return Coord(x=7, y=8)

    def own_goal_position(self, player_id):
        return Coord(x=9, y=10)

    def opponent_goal_position(self, player_id):
        return Coord(x=11, y=12)

    def player_position(self, player_id):
        return self.position

    def player_has_ball(self, player_id):
        return self.has_ball

    def team_has_ball(self, player_id):
        return self.has_ball

    def is_inside_field(self, position):
        return self.inside_field

    def player_is_on_field(self, player_id):
        return self.on_field

    def apply_pass(self, player_id, destination):
        self.actions.append(("pass", player_id, destination))

    def apply_shot(self, player_id, destination):
        self.actions.append(("shot", player_id, destination))

    def apply_movement(self, player_id, destination):
        self.actions.append(("movement", player_id, destination))

    def assigned_behavior(self, player_id):
        return self.behavior_id

    def register_error(self, player_id, message):
        self.errors.append((player_id, message))


def test_ejecuta_el_codigo_del_comportamiento_asignado(monkeypatch) -> None:
    motor = MotorDePrueba()
    def behavior(player: JugadorAPI) -> None:
        player.pasar(player.encontrar_arco_enemigo())

    recibidos: list[str] = []

    def obtener(behavior_id: str) -> Callable:
        recibidos.append(behavior_id)
        return behavior

    monkeypatch.setattr(executor, "obtener_funcion_comportamiento", obtener)

    executor.ejecutar_comportamiento("jugador-1", motor)

    assert recibidos == ["behavior-asignado"]
    assert motor.actions == [("pass", "jugador-1", Coord(x=11, y=12))]
    assert motor.errors == []


def test_comportamiento_preprogramado_se_precarga_y_ejecuta(monkeypatch) -> None:
    from sqlalchemy import create_engine
    from sqlalchemy.orm import Session

    import app.models  # noqa: F401 - registra las tablas
    from app.db.base import Base

    engine_db = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine_db)
    db = Session(engine_db)
    behavior = Behavior(
        name="Preprogramado de prueba",
        code="def behavior(player):\n    player.correr(player.encontrar_pelota())",
        is_preprogrammed=True,
    )
    db.add(behavior)
    db.commit()
    monkeypatch.setattr(loader, "_cache", {})

    loader.precargar_preprogramados(db)
    motor = MotorDePrueba(behavior_id=behavior.id)
    motor.has_ball = False
    monkeypatch.setattr(
        executor, "obtener_funcion_comportamiento", loader.obtener_funcion_comportamiento
    )

    executor.ejecutar_comportamiento("jugador-1", motor)

    assert motor.actions == [("movement", "jugador-1", motor.ball)]
    assert motor.errors == []
    db.close()
    engine_db.dispose()


@pytest.mark.parametrize("accion", ["pasar", "patear_pelota"])
def test_no_aplica_pase_o_tiro_si_destino_esta_fuera_de_cancha(accion: str) -> None:
    motor = MotorDePrueba()
    motor.inside_field = False
    jugador = JugadorAPI("jugador-1", motor)

    getattr(jugador, accion)(Coord(x=100, y=100))

    assert motor.actions == []


def test_valida_tambien_la_posesion_y_que_el_jugador_siga_en_cancha() -> None:
    motor = MotorDePrueba()
    jugador = JugadorAPI("jugador-1", motor)

    motor.has_ball = False
    jugador.pasar(Coord(x=1, y=1))
    jugador.patear_pelota(Coord(x=1, y=1))
    motor.has_ball = True
    motor.on_field = False
    jugador.correr(Coord(x=1, y=1))

    assert motor.actions == []


def test_comportamiento_inexistente_se_registra_y_no_finaliza_el_partido(monkeypatch) -> None:
    motor = MotorDePrueba()

    def obtener(_behavior_id: str):
        raise ComportamientoNoEncontrado("inexistente")

    monkeypatch.setattr(executor, "obtener_funcion_comportamiento", obtener)

    executor.ejecutar_comportamiento("jugador-1", motor)

    assert motor.errors == [("jugador-1", "inexistente")]
    assert motor.actions == []
    assert motor.finished is False


def test_excepcion_del_codigo_se_controla_y_no_finaliza_el_partido(monkeypatch) -> None:
    motor = MotorDePrueba()

    def behavior(_player: JugadorAPI) -> None:
        raise RuntimeError("fallo del script")

    monkeypatch.setattr(executor, "obtener_funcion_comportamiento", lambda _id: behavior)

    executor.ejecutar_comportamiento("jugador-1", motor)

    assert motor.errors == [("jugador-1", "excepcion: fallo del script")]
    assert motor.actions == []
    assert motor.finished is False


def test_acciones_publicas_quedan_limitadas_al_jugador_que_recibe_la_api() -> None:
    motor = MotorDePrueba()
    jugador = JugadorAPI("jugador-1", motor)

    jugador.correr(Coord(x=2, y=3))
    jugador.patear_pelota(Coord(x=4, y=5))

    assert motor.actions == [
        ("movement", "jugador-1", Coord(x=2, y=3)),
        ("shot", "jugador-1", Coord(x=4, y=5)),
    ]

@pytest.mark.parametrize("has_ball", [True, False])
def test_comportamientos_iniciales_se_precargan_y_ejecutan(db, monkeypatch, has_ball):
    from sqlalchemy import select
    from app.db.init_db import cargar_comportamientos_por_defecto

    monkeypatch.setattr(loader, "_cache", {})
    assert cargar_comportamientos_por_defecto(db) == 3
    loader.precargar_preprogramados(db)
    for behavior in db.scalars(select(Behavior)).all():
        motor = MotorDePrueba(behavior_id=behavior.id)
        motor.has_ball = has_ball
        executor.ejecutar_comportamiento("jugador-1", motor)
        assert motor.errors == []
        assert len(motor.actions) == 1
