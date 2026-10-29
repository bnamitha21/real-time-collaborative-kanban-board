from pydantic import BaseModel, ConfigDict, Field


class CreateOrgSchema(BaseModel):
    model_config = ConfigDict(extra="forbid")
    name: str = Field(..., min_length=1, max_length=120)


class UpdateOrgSchema(BaseModel):
    model_config = ConfigDict(extra="forbid")
    name: str = Field(..., min_length=1, max_length=120)
