from pydantic import BaseModel, ConfigDict
from pydantic.alias_generators import to_camel

"""Esquemas del chequeo de salud de la API."""

class HealthRead(BaseModel):
    """Respuesta de `GET /api/health`.
    """

    model_config = ConfigDict(alias_generator=to_camel, populate_by_name=True)

    status: str
    database_connected: bool