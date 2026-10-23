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
