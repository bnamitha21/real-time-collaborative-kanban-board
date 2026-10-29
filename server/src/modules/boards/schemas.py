from pydantic import BaseModel, ConfigDict, Field


class CreateBoardSchema(BaseModel):
    model_config = ConfigDict(extra="forbid")
    name: str = Field(..., min_length=1, max_length=120)


class UpdateBoardSchema(BaseModel):
    model_config = ConfigDict(extra="forbid")
    name: str = Field(..., min_length=1, max_length=120)


class ListBoardsQuerySchema(BaseModel):
    model_config = ConfigDict(extra="forbid")
    limit: int | None = Field(default=50, ge=1, le=100)
    cursor: str | None = None
