from __future__ import annotations

from datetime import datetime
from typing import Any, ClassVar

from pydantic import BaseModel, ConfigDict, Field


class ServerOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str
    transport: str
    config: dict[str, Any]
    created_at: datetime


class ScenarioOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    __test__: ClassVar[bool] = False  # not a pytest test class despite the name

    id: int
    name: str
    server: str
    tool: str
    input: dict[str, Any]
    assertions: dict[str, Any]
    created_at: datetime


class AssertionResultOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    assertion: str
    expected: Any
    actual: Any
    passed: bool
    message: str


class TestResultOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    __test__: ClassVar[bool] = False  # not a pytest test class despite the name

    id: int
    scenario: str
    server: str
    tool: str
    status: str
    duration_seconds: float
    assertions: list[AssertionResultOut]
    error: str | None
    response: dict[str, Any] | None


class RunSummaryOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    status: str
    passed: int
    failed: int
    errored: int
    created_at: datetime


class RunDetailOut(RunSummaryOut):
    results: list[TestResultOut]


class RunCreateRequest(BaseModel):
    scenario_ids: list[int] = Field(min_length=1)
