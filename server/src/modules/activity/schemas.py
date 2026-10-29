from pydantic import BaseModel, ConfigDict, Field


class ActivityQuerySchema(BaseModel):
    model_config = ConfigDict(extra="forbid")
    boardId: str | None = None
    taskId: str | None = None
    cursor: str | None = None
    limit: int | None = Field(default=50, ge=1, le=100)
