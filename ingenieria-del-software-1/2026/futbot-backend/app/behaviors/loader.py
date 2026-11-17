import logging
from typing import Callable

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.behaviors.errors import ComportamientoInvalido, ComportamientoNoEncontrado
from app.models.behavior import Behavior

logger = logging.getLogger(__name__)

"""Carga y cachea, en memoria, las funciones `comportamiento` ya compiladas.
"""

# Builtins minimos que puede usar el codigo de un comportamiento.
BUILTINS_RESTRINGIDOS = {
    "range": range,
    "len": len,
    "abs": abs,
    "min": min,
    "max": max,
}

_cache: dict[str, Callable] = {}


def precargar_preprogramados(db: Session) -> None:
    """Compila los comportamientos preprogramados y los deja en `_cache`.
    """
    preprogramados = db.scalars(
        select(Behavior).where(
            Behavior.is_preprogrammed.is_(True), Behavior.deleted_at.is_(None)
        )
    ).all()

    for behavior in preprogramados:
        namespace: dict = {"__builtins__": BUILTINS_RESTRINGIDOS}
        exec(behavior.code, namespace)  # noqa: S102 -- codigo propio, no de usuario
        funcion = namespace.get("behavior")
        if not callable(funcion):
            raise ComportamientoInvalido(behavior.id)
        _cache[behavior.id] = funcion
        logger.info(
            "Comportamiento compilado y cacheado: %s (%s)", behavior.name, behavior.id
        )


def obtener_funcion_comportamiento(behavior_id: str) -> Callable:
    """Devuelve la funcion `comportamiento` ya compilada, sin tocar la base."""
    funcion = _cache.get(behavior_id)
    if funcion is None:
        raise ComportamientoNoEncontrado(behavior_id)
    return funcion

def compile_and_cache_behavior(behavior_id: str, code:str, overwrite: bool = False,) -> callable:
    """Compila el código de un comportamiento y lo cachea en memoria."""
    if behavior_id in _cache and not overwrite:
        return _cache[behavior_id]
    namespace: dict = {"__builtins__": BUILTINS_RESTRINGIDOS}
    try:
        exec(code, namespace)  # noqa: S102 -- codigo propio, no de usuario
        behavior_function = namespace.get("behavior")
        if not callable(behavior_function):
            raise ComportamientoInvalido(behavior_id)
        _cache[behavior_id] = behavior_function
        return behavior_function
    except Exception as e:
        logger.error("Error al compilar el comportamiento: %s", behavior_id, exc_info=True)
        raise ComportamientoInvalido(behavior_id)