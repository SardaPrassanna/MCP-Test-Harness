from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field


class ScenarioResult(BaseModel):
    """The structured outcome of executing a single `TestScenario`.

    `status` is:
      - "passed": the tool was called and every assertion held.
      - "failed": the tool was called but at least one assertion did not
        hold; `failures` explains each one.
      - "error": the scenario could not be evaluated at all (connection
        failure, timeout, or an unexpected exception); `error` explains why,
        and `failures`/`response` are unset since no assertions ran.
    """

    model_config = ConfigDict(frozen=True)

    scenario: str
    server: str
    tool: str
    status: Literal["passed", "failed", "error"]
    duration_seconds: float = Field(ge=0)
    failures: list[str] = Field(default_factory=list)
    error: str | None = None
    response: dict[str, Any] | None = None
