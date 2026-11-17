from pydantic import BaseModel, ConfigDict, Field

class SimulationTicketCreate(BaseModel):
    player_id: str = Field(min_length=1)
    behavior_id: str = Field(min_length=1)

    model_config = ConfigDict(extra="forbid")

class SimulationTicketRead(BaseModel):
    ticket: str