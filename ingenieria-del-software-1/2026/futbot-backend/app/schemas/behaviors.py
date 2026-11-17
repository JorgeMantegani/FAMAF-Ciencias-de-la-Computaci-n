from pydantic import BaseModel, ConfigDict, Field
from pydantic.alias_generators import to_camel

class BehaviorRead(BaseModel): # Como lo voy a devolver al front (en route hago list[BehaviorRead])
    id: str
    name: str
    code: str
    is_default: bool = Field(validation_alias="is_preprogrammed")
    
    model_config = ConfigDict(
        alias_generator=to_camel, 
        populate_by_name=True, 
        from_attributes=True
    )
class BehaviorCreate(BaseModel): # Como lo voy a recibir del front (en route hago BehaviorCreate)
    name: str = Field(min_length=1, max_length=50)
    code: str = Field(min_length=1)
    
    model_config = ConfigDict(
        alias_generator=to_camel, 
        populate_by_name=True,
        extra="forbid"
    )

class BehaviorUpdate(BaseModel): # Como lo voy a recibir del front (en route hago BehaviorUpdate)
    name: str = Field(min_length=1, max_length=50)
    code: str = Field(min_length=1)
    
    model_config = ConfigDict(
        alias_generator=to_camel, 
        populate_by_name=True,
        extra="forbid"
    )