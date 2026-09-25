from __future__ import annotations

from typing import Any, ClassVar, Literal

from pydantic import BaseModel, ConfigDict, Field


class AssertionResult(BaseModel):
    """The outcome of checking a single declarative assertion.

    `expected` and `actual` are always populated, whether the check passed
    or not, so a result explains itself without needing to be re-run.
    """

    model_config = ConfigDict(frozen=True)

    assertion: str
    expected: Any
    actual: Any
    passed: bool
    message: str


class TestResult(BaseModel):
    """The structured outcome of executing a single `TestScenario`.

    `status` is:
      - "passed": the tool was called and every assertion held.
      - "failed": the tool was called but at least one assertion did not
        hold; `assertions` (via `failures`) explains each one.
      - "error": the scenario could not be evaluated at all (connection
        failure, timeout, or an unexpected exception); `error` explains
        why, and `assertions`/`response` are unset since no assertions ran.
    """

    model_config = ConfigDict(frozen=True)
    __test__: ClassVar[bool] = False  # not a pytest test class despite the name

    scenario: str
    server: str
    tool: str
    status: Literal["passed", "failed", "error"]
    duration_seconds: float = Field(ge=0)
    assertions: list[AssertionResult] = Field(default_factory=list)
    error: str | None = None
    response: dict[str, Any] | None = None

    @property
    def failures(self) -> list[AssertionResult]:
        """The subset of `assertions` that did not pass."""
        return [result for result in self.assertions if not result.passed]


class TestRunResult(BaseModel):
    """The aggregated outcome of executing a batch of scenarios."""

    model_config = ConfigDict(frozen=True)
    __test__: ClassVar[bool] = False  # not a pytest test class despite the name

    results: list[TestResult]
    passed: int = Field(ge=0)
    failed: int = Field(ge=0)
    errored: int = Field(ge=0)

    @property
    def total(self) -> int:
        return len(self.results)

    @property
    def status(self) -> Literal["passed", "failed"]:
        return "passed" if self.failed == 0 and self.errored == 0 else "failed"

    @classmethod
    def from_results(cls, results: list[TestResult]) -> TestRunResult:
        """Aggregate a list of `TestResult`s into one `TestRunResult`."""
        return cls(
            results=results,
            passed=sum(1 for result in results if result.status == "passed"),
            failed=sum(1 for result in results if result.status == "failed"),
            errored=sum(1 for result in results if result.status == "error"),
        )
