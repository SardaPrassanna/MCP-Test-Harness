from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session

from mcp_test_harness.models.scenario import TestScenario
from mcp_test_harness.storage.models import ScenarioRecord


class ScenarioNotFoundError(Exception):
    """Raised when a referenced scenario id has no stored record."""


def create_scenario(db: Session, scenario: TestScenario) -> ScenarioRecord:
    record = ScenarioRecord(
        name=scenario.name,
        server=scenario.server,
        tool=scenario.tool,
        input=scenario.input,
        assertions=scenario.assertions.model_dump(mode="json", exclude_none=True),
    )
    db.add(record)
    db.flush()
    db.refresh(record)
    return record


def list_scenarios(db: Session) -> list[ScenarioRecord]:
    return list(db.scalars(select(ScenarioRecord).order_by(ScenarioRecord.id)))


def get_scenario(db: Session, scenario_id: int) -> ScenarioRecord:
    record = db.get(ScenarioRecord, scenario_id)
    if record is None:
        raise ScenarioNotFoundError(f"no scenario with id {scenario_id}")
    return record


def to_test_scenario(record: ScenarioRecord) -> TestScenario:
    """Rebuild the validated `TestScenario` a stored `ScenarioRecord` was created from."""
    return TestScenario.model_validate(
        {
            "name": record.name,
            "server": record.server,
            "tool": record.tool,
            "input": record.input,
            "assertions": record.assertions,
        }
    )
