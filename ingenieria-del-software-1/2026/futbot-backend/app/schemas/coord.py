from pydantic import BaseModel


class Coord(BaseModel):
    """Coordenada cartesiana de la cancha.

    {"x": 0.0, "y": 0.0} es el centro de la cancha. Mismo sistema de
    unidades que usa SIMULATION_TICK por WebSocket (ver API/Contrato
    WebSocket), para no tener que convertir nada al armar ese payload.
    """

    x: float
    y: float

    model_config = {"frozen": True}