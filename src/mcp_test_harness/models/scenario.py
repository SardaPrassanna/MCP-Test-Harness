from __future__ import annotations

from typing import Any, ClassVar, Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator


class ScenarioAssertions(BaseModel):
    """Declarative expectations checked against a tool call's result.

    Only this fixed, explicit set of assertion kinds is supported; unknown
    keys are rejected so a typo in a scenario file fails loudly instead of
    silently asserting nothing.
    """

    model_config = ConfigDict(extra="forbid")

    status: Literal["success", "error"] | None = None
    min_items: int | None = Field(default=None, ge=0)
    max_items: int | None = Field(default=None, ge=0)
    equals: Any = None
    contains: Any = None

    @model_validator(mode="after")
    def _require_at_least_one_check(self) -> ScenarioAssertions:
        known_checks = {"status", "min_items", "max_items", "equals", "contains"}
        if not self.model_fields_set & known_checks:
            raise ValueError("assertions must specify at least one check")
        return self

    @model_validator(mode="after")
    def _validate_item_count_bounds(self) -> ScenarioAssertions:
        if (
            self.min_items is not None
            and self.max_items is not None
            and self.min_items > self.max_items
        ):
            raise ValueError("min_items must not be greater than max_items")
        return self


class TestScenario(BaseModel):
    """A single declarative MCP tool-call test scenario.

    Example:
        name: list_users
        server: demo
        tool: list_users
        input:
          limit: 5
        assertions:
          status: success
          min_items: 1
    """

    model_config = ConfigDict(extra="forbid")
    __test__: ClassVar[bool] = False  # not a pytest test class despite the name

    name: str = Field(min_length=1)
    server: str = Field(min_length=1)
    tool: str = Field(min_length=1)
    input: dict[str, Any] = Field(default_factory=dict)
    assertions: ScenarioAssertions
