from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


class CreateTenantSchema(BaseModel):
    model_config = ConfigDict(extra="forbid")
    name: str = Field(..., min_length=1, max_length=120)


class UpdateTenantSchema(BaseModel):
    model_config = ConfigDict(extra="forbid")
    name: str = Field(..., min_length=1, max_length=120)


class AddMemberSchema(BaseModel):
    model_config = ConfigDict(extra="forbid")
    email: str
    role: Literal["tenant_admin", "member"]
