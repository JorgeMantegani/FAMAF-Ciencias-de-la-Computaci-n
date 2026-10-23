import concurrent.futures
import logging

from app.behaviors.api import JugadorAPI
from app.behaviors.errors import ComportamientoNoEncontrado
from app.behaviors.interfaces import IMatchEngine
from app.behaviors.loader import obtener_funcion_comportamiento

logger = logging.getLogger(__name__)

# Timeout por jugador por tick. Con ThreadPoolExecutor un comportamiento realmente colgado no se puede matar de verdad 
TIMEOUT_SEGUNDOS = 0.05

_pool = concurrent.futures.ThreadPoolExecutor(max_workers=8)

"""Punto de entrada publico del modulo de comportamientos.
"""

def ejecutar_comportamiento(player_id: str, engine: IMatchEngine) -> None:
    """Ejecuta, para un jugador puntual, el comportamiento que tiene asignado.
    """
    behavior_id = engine.assigned_behavior(player_id)

    try:
        funcion = obtener_funcion_comportamiento(behavior_id)
    except ComportamientoNoEncontrado as e:
        logger.warning("Comportamiento no encontrado para %s: %s", player_id, e)
        engine.register_error(player_id, str(e))
        return

    proxy = JugadorAPI(player_id, engine)
    future = _pool.submit(funcion, proxy)

    try:
        future.result(timeout=TIMEOUT_SEGUNDOS)
    except concurrent.futures.TimeoutError:
        logger.warning("Timeout ejecutando comportamiento de %s", player_id)
        engine.register_error(player_id, "timeout")
    except Exception as e:  # noqa: BLE001 -- cualquier error del codigo ejecutado
        logger.warning(
            "Excepcion ejecutando comportamiento de %s: %s", player_id, e
        )
        engine.register_error(player_id, f"excepcion: {e}")