from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


class CreateTaskSchema(BaseModel):
    model_config = ConfigDict(extra="forbid")
    columnId: str
    title: str = Field(..., min_length=1, max_length=200)
    description: str | None = Field(default="", max_length=10000)
    assigneeId: str | None = None
    priority: Literal["low", "medium", "high"] | None = "medium"
    actionId: str | None = None


class UpdateTaskSchema(BaseModel):
    model_config = ConfigDict(extra="forbid")
    expectedVersion: int
    actionId: str | None = None
    title: str | None = Field(default=None, min_length=1, max_length=200)
    description: str | None = Field(default=None, max_length=10000)
    assigneeId: str | None = None
    priority: Literal["low", "medium", "high"] | None = None


class DeleteTaskQuerySchema(BaseModel):
    model_config = ConfigDict(extra="forbid")
    expectedVersion: int
    actionId: str | None = None
