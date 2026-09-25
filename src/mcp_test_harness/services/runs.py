from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session

from mcp_test_harness.models.result import TestResult, TestRunResult
from mcp_test_harness.runner.engine import run_scenario
from mcp_test_harness.services.scenarios import get_scenario, to_test_scenario
from mcp_test_harness.services.servers import get_server_config
from mcp_test_harness.storage.models import TestResultRecord, TestRunRecord


class RunNotFoundError(Exception):
    """Raised when a referenced run id has no stored record."""


async def execute_run(db: Session, scenario_ids: list[int]) -> TestRunRecord:
    """Run every scenario in `scenario_ids` and persist the aggregated outcome.

    Looks up each scenario and its referenced server by their stored
    records, executes it via `run_scenario`, and stores both the run
    summary and each individual result. Raises `ScenarioNotFoundError` /
    `ServerNotFoundError` (propagated from the lookups) before running
    anything if a scenario id or its server isn't registered.
    """
    results: list[TestResult] = []
    for scenario_id in scenario_ids:
        scenario = to_test_scenario(get_scenario(db, scenario_id))
        server_config = get_server_config(db, scenario.server)
        results.append(await run_scenario(scenario, server_config))

    run_result = TestRunResult.from_results(results)

    run_record = TestRunRecord(
        status=run_result.status,
        passed=run_result.passed,
        failed=run_result.failed,
        errored=run_result.errored,
    )
    run_record.results = [
        TestResultRecord(
            scenario=result.scenario,
            server=result.server,
            tool=result.tool,
            status=result.status,
            duration_seconds=result.duration_seconds,
            assertions=[assertion.model_dump(mode="json") for assertion in result.assertions],
            error=result.error,
            response=result.response,
        )
        for result in results
    ]

    db.add(run_record)
    db.flush()
    db.refresh(run_record)
    return run_record


def list_runs(db: Session) -> list[TestRunRecord]:
    return list(db.scalars(select(TestRunRecord).order_by(TestRunRecord.id)))


def get_run(db: Session, run_id: int) -> TestRunRecord:
    record = db.get(TestRunRecord, run_id)
    if record is None:
        raise RunNotFoundError(f"no run with id {run_id}")
    return record
