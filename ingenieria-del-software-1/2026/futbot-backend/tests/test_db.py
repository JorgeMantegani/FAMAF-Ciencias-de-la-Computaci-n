import pytest
from sqlalchemy import Engine, func, inspect, select, text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.db.init_db import _leer_comportamiento, cargar_comportamientos_por_defecto
from app.models.behavior import Behavior
from app.models.club import Club
from app.models.player import Player
from tests.conftest import crear_player

"""Tests del schema: tablas, restricciones de integridad y carga inicial."""

TABLAS_ESPERADAS = {
    "users",
    "auth_sessions",
    "clubs",
    "players",
    "behaviors",
    "rooms",
    "enrollments",
    "squad_entries",
    "matches",
    "match_players",
    "goals",
}


def test_se_crean_las_tablas_esperadas(engine: Engine) -> None:
    """El schema generado tiene exactamente las tablas esperadas.
    """
    assert set(inspect(engine).get_table_names()) == TABLAS_ESPERADAS


def test_las_claves_foraneas_estan_activadas(engine: Engine) -> None:
    """SQLite verifica las claves foraneas en las conexiones de la aplicacion.
    """
    with engine.connect() as conexion:
        assert conexion.execute(text("PRAGMA foreign_keys")).scalar() == 1


def test_borrar_un_club_borra_sus_jugadores(db: Session, club: Club, crear_player) -> None:
    """La cascada de la FK funciona de verdad, no solo en el modelo."""
    crear_player(club.id)
    assert db.scalar(select(func.count()).select_from(Player)) == 1

    db.delete(club)
    db.commit()

    assert db.scalar(select(func.count()).select_from(Player)) == 0


def test_rechaza_un_jugador_de_un_club_inexistente(crear_player) -> None:
    """Una clave foranea que apunta a la nada es rechazada por la base."""
    with pytest.raises(IntegrityError):
        crear_player(club_id="club-que-no-existe")


def test_rechaza_pacss_que_no_suma_trescientos(club: Club, crear_player) -> None:
    """El CHECK de la suma PACSS es la red de seguridad detras de Pydantic.
    """
    with pytest.raises(IntegrityError):
        # 61 + 60 + 60 + 60 + 60 = 301
        crear_player(club.id, power=61)


def test_rechaza_un_atributo_fuera_del_rango_permitido(
    club: Club, crear_player
) -> None:
    """Ningun atributo PACSS puede salirse de 20 a 100, aunque la suma cierre."""
    with pytest.raises(IntegrityError):
        # La suma sigue siendo 300, pero strength queda en 10 y power en 110 los dos fuera del rango.
        crear_player(club.id, power=110, strength=10)


def test_un_comportamiento_preprogramado_no_puede_tener_club(
    db: Session, club: Club
) -> None:
    """`is_preprogrammed` y `club_id IS NULL` no se pueden contradecir."""
    with pytest.raises(IntegrityError):
        db.add(
            Behavior(
                club_id=club.id,
                name="mal_marcado",
                code="def comportamiento(jugador): pass",
                is_preprogrammed=True,
            )
        )
        db.commit()


def test_la_carga_inicial_deja_los_tres_comportamientos(db: Session) -> None:
    """El seed carga los comportamientos preprogramados del sistema."""
    cantidad = cargar_comportamientos_por_defecto(db)

    assert cantidad == 3

    nombres = set(
        db.scalars(select(Behavior.name).where(Behavior.club_id.is_(None))).all()
    )
    assert nombres == {"front", "defense", "goalkeeper"}

    # Todos quedan marcados como preprogramados, con su codigo cargado.
    for comportamiento in db.scalars(select(Behavior)).all():
        assert comportamiento.is_preprogrammed is True
        assert comportamiento.code


def test_la_carga_inicial_no_duplica_al_repetirse(db: Session) -> None:
    """Ejecutar el seed varias veces deja siempre las mismas tres filas.
    """
    cargar_comportamientos_por_defecto(db)
    cargar_comportamientos_por_defecto(db)
    cantidad = cargar_comportamientos_por_defecto(db)

    assert cantidad == 3
    assert db.scalar(select(func.count()).select_from(Behavior)) == 3


@pytest.mark.parametrize("codigo", ["", " \n\t"])
def test_rechaza_archivos_de_comportamiento_vacios(tmp_path, codigo) -> None:
    archivo = tmp_path / "vacio.py"
    archivo.write_text(codigo, encoding="utf-8")
    with pytest.raises(ValueError, match="vacio.py tiene codigo vacio"):
        _leer_comportamiento(archivo)
