from pydantic import BaseModel, ConfigDict, Field


# Ticket: BE [BE] Endpoint Create Club Player
# Contract - Payload request
class PlayerCreate(BaseModel):
    name: str = Field(min_length=3)
    power: int
    agility: int
    control: int
    speed: int
    strength: int

# Contract - Successful response
class PlayerResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    name: str
    power: int
    agility: int
    control: int
    speed: int
    strength: int
    is_playing: bool
