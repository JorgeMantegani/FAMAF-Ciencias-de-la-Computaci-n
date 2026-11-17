import pytest

from app.behaviors.loader import obtener_funcion_comportamiento
from app.db.base import ahora_utc
from app.models.behavior import Behavior
from app.services.behavior_change_service import behavior_belongs_to_club, compile_behavior


def make_behavior(db, club_id, name="Mi comportamiento", deleted=False):
    behavior = Behavior(
        club_id=club_id,
        name=name,
        code="def behavior(player):\n    pass",
        is_preprogrammed=club_id is None,
        deleted_at=ahora_utc() if deleted else None,
    )
    db.add(behavior)
    db.commit()
    return behavior


def test_own_behavior_is_valid(db, club):
    behavior = make_behavior(db, club.id)
    assert behavior_belongs_to_club(db, behavior.id, club.id) is True


def test_preprogrammed_behavior_is_valid(db, club, comportamiento_prueba):
    assert behavior_belongs_to_club(db, comportamiento_prueba.id, club.id) is True


def test_behavior_of_other_club_is_invalid(db, club, other_club):
    behavior = make_behavior(db, other_club.id)
    assert behavior_belongs_to_club(db, behavior.id, club.id) is False


def test_deleted_behavior_is_invalid(db, club):
    behavior = make_behavior(db, club.id, deleted=True)
    assert behavior_belongs_to_club(db, behavior.id, club.id) is False


def test_unknown_behavior_is_invalid(db, club):
    assert behavior_belongs_to_club(db, "no-existe", club.id) is False

def test_club_behavior_is_compiled_and_cached(db, club):
    behavior = make_behavior(db, club.id)
    assert compile_behavior(db, behavior.id) is True
    assert callable(obtener_funcion_comportamiento(behavior.id))


def test_invalid_code_is_not_compiled(db, club):
    behavior = make_behavior(db, club.id)
    behavior.code = "esto no es python"
    db.commit()
    assert compile_behavior(db, behavior.id) is False


def test_preprogrammed_is_not_recompiled(db, comportamiento_prueba):
    assert compile_behavior(db, comportamiento_prueba.id) is True


def test_unknown_behavior_is_not_compiled(db):
    assert compile_behavior(db, "no-existe") is False