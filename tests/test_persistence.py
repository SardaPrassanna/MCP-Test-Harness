"""Persistence-layer tests: the services + SQLAlchemy models, independent of
the HTTP layer.

Each test binds to its own scratch SQLite database file under `tmp_path`
via `build_session_factory` -- never the project's real
`mcp_test_harness.db` -- so no state ever leaks between tests.
"""

from collections.abc import Callable, Generator
from pathlib import Path

import pytest
from pydantic import ValidationError
from sqlalchemy.orm import Session

from mcp_test_harness.models.scenario import TestScenario
from mcp_test_harness.models.server import StdioServerConfig
from mcp_test_harness.services.runs import RunNotFoundError, execute_run, get_run, list_runs
from mcp_test_harness.services.scenarios import (
    ScenarioNotFoundError,
    create_scenario,
    get_scenario,
    list_scenarios,
    to_test_scenario,
)
from mcp_test_harness.services.servers import (
    ServerAlreadyExistsError,
    ServerNotFoundError,
    create_server,
    get_server_config,
    list_servers,
)
from mcp_test_harness.storage.database import build_session_factory

StdioConfigFactory = Callable[..., StdioServerConfig]


@pytest.fixture
def db_session(tmp_path: Path) -> Generator[Session, None, None]:
    factory = build_session_factory(f"sqlite:///{(tmp_path / 'test.db').as_posix()}")
    session = factory()
    try:
        yield session
    finally:
        session.close()


def _scenario(**overrides: object) -> TestScenario:
    data: dict[str, object] = {
        "name": "echo_scenario",
        "server": "fake-stdio-server",
        "tool": "echo",
        "input": {"text": "hello"},
        "assertions": {"status": "success", "equals": "hello"},
    }
    data.update(overrides)
    return TestScenario.model_validate(data)


# 1. Create server ----------------------------------------------------------------


def test_create_server_persists_all_fields(
    db_session: Session, stdio_config_factory: StdioConfigFactory
) -> None:
    config = stdio_config_factory()

    record = create_server(db_session, config)

    assert record.id is not None
    assert record.name == config.name
    assert record.transport == "stdio"
    assert record.config["command"] == config.command
    assert record.created_at is not None


def test_create_server_rejects_duplicate_name(
    db_session: Session, stdio_config_factory: StdioConfigFactory
) -> None:
    create_server(db_session, stdio_config_factory())

    with pytest.raises(ServerAlreadyExistsError):
        create_server(db_session, stdio_config_factory())


# 2. List servers -----------------------------------------------------------------


def test_list_servers_returns_all_in_creation_order(
    db_session: Session, stdio_config_factory: StdioConfigFactory
) -> None:
    create_server(db_session, stdio_config_factory(name="server-a"))
    create_server(db_session, stdio_config_factory(name="server-b"))

    servers = list_servers(db_session)

    assert [server.name for server in servers] == ["server-a", "server-b"]


def test_list_servers_is_empty_for_a_fresh_database(db_session: Session) -> None:
    assert list_servers(db_session) == []


def test_get_server_config_rebuilds_a_valid_server_config(
    db_session: Session, stdio_config_factory: StdioConfigFactory
) -> None:
    create_server(db_session, stdio_config_factory())

    config = get_server_config(db_session, "fake-stdio-server")

    assert isinstance(config, StdioServerConfig)
    assert config.name == "fake-stdio-server"


def test_get_server_config_raises_for_unknown_name(db_session: Session) -> None:
    with pytest.raises(ServerNotFoundError):
        get_server_config(db_session, "does-not-exist")


# 3. Create scenario ----------------------------------------------------------------


def test_create_scenario_round_trips_through_storage(db_session: Session) -> None:
    scenario = _scenario()

    record = create_scenario(db_session, scenario)

    assert record.id is not None
    assert to_test_scenario(record) == scenario


def test_list_scenarios_returns_all_in_creation_order(db_session: Session) -> None:
    create_scenario(db_session, _scenario(name="first"))
    create_scenario(db_session, _scenario(name="second"))

    scenarios = list_scenarios(db_session)

    assert [record.name for record in scenarios] == ["first", "second"]


def test_get_scenario_raises_for_unknown_id(db_session: Session) -> None:
    with pytest.raises(ScenarioNotFoundError):
        get_scenario(db_session, 999)


# 4. Invalid scenario ----------------------------------------------------------------


@pytest.mark.parametrize(
    "overrides",
    [
        {"tool": None},
        {"assertions": {}},
        {"assertions": {"min_items": -1}},
        {"assertions": {"min_items": 5, "max_items": 1}},
        {"unexpected_field": "nope"},
        {"name": ""},
    ],
    ids=[
        "null_tool",
        "empty_assertions",
        "negative_min_items",
        "min_over_max",
        "extra_field",
        "blank_name",
    ],
)
def test_invalid_scenarios_are_rejected(overrides: dict[str, object]) -> None:
    data: dict[str, object] = {
        "name": "echo_scenario",
        "server": "fake-stdio-server",
        "tool": "echo",
        "input": {"text": "hello"},
        "assertions": {"status": "success"},
    }
    data.update(overrides)

    with pytest.raises(ValidationError):
        TestScenario.model_validate(data)


# 5. Execute run / 6. persisted result -----------------------------------------------


async def test_execute_run_persists_a_result_matching_the_engine_outcome(
    db_session: Session, stdio_config_factory: StdioConfigFactory
) -> None:
    create_server(db_session, stdio_config_factory())
    scenario_record = create_scenario(db_session, _scenario())

    run_record = await execute_run(db_session, [scenario_record.id])

    assert run_record.id is not None
    assert run_record.status == "passed"
    assert (run_record.passed, run_record.failed, run_record.errored) == (1, 0, 0)
    assert len(run_record.results) == 1

    result_record = run_record.results[0]
    assert result_record.run_id == run_record.id
    assert result_record.scenario == "echo_scenario"
    assert result_record.server == "fake-stdio-server"
    assert result_record.tool == "echo"
    assert result_record.status == "passed"
    assert result_record.duration_seconds >= 0
    assert result_record.error is None
    assert result_record.response is not None
    assert result_record.response["is_error"] is False
    assert [assertion["assertion"] for assertion in result_record.assertions] == [
        "status",
        "equals",
    ]
    assert all(assertion["passed"] for assertion in result_record.assertions)


async def test_execute_run_persists_a_failed_result_with_failure_detail(
    db_session: Session, stdio_config_factory: StdioConfigFactory
) -> None:
    create_server(db_session, stdio_config_factory())
    scenario_record = create_scenario(db_session, _scenario(assertions={"equals": "goodbye"}))

    run_record = await execute_run(db_session, [scenario_record.id])

    assert run_record.status == "failed"
    assert (run_record.passed, run_record.failed, run_record.errored) == (0, 1, 0)
    failing_assertion = run_record.results[0].assertions[0]
    assert failing_assertion["passed"] is False
    assert failing_assertion["expected"] == "goodbye"
    assert failing_assertion["actual"] == "hello"


async def test_execute_run_raises_for_unknown_scenario_id(db_session: Session) -> None:
    with pytest.raises(ScenarioNotFoundError):
        await execute_run(db_session, [999])


async def test_execute_run_raises_for_scenario_referencing_unregistered_server(
    db_session: Session,
) -> None:
    scenario_record = create_scenario(db_session, _scenario(server="never-registered"))

    with pytest.raises(ServerNotFoundError):
        await execute_run(db_session, [scenario_record.id])


# 7. Retrieve run ------------------------------------------------------------------------


async def test_get_run_returns_the_persisted_run(
    db_session: Session, stdio_config_factory: StdioConfigFactory
) -> None:
    create_server(db_session, stdio_config_factory())
    scenario_record = create_scenario(db_session, _scenario())
    run_record = await execute_run(db_session, [scenario_record.id])

    fetched = get_run(db_session, run_record.id)

    assert fetched.id == run_record.id
    assert len(fetched.results) == 1


async def test_list_runs_returns_all_in_creation_order(
    db_session: Session, stdio_config_factory: StdioConfigFactory
) -> None:
    create_server(db_session, stdio_config_factory())
    scenario_record = create_scenario(db_session, _scenario())
    first = await execute_run(db_session, [scenario_record.id])
    second = await execute_run(db_session, [scenario_record.id])

    runs = list_runs(db_session)

    assert [run.id for run in runs] == [first.id, second.id]


# 8. Missing run ---------------------------------------------------------------------------


def test_get_run_raises_for_unknown_id(db_session: Session) -> None:
    with pytest.raises(RunNotFoundError):
        get_run(db_session, 999)


# 9. Database isolation between tests ------------------------------------------------------


def test_database_starts_empty_for_every_test(db_session: Session) -> None:
    """Guards against test pollution: several tests in this file register a
    server or scenario under the same name, so if isolation ever broke
    (e.g. a shared module-level engine), this would see leftover rows."""
    assert list_servers(db_session) == []
    assert list_scenarios(db_session) == []
    assert list_runs(db_session) == []


def test_sessions_on_different_database_files_do_not_share_state(
    tmp_path: Path, stdio_config_factory: StdioConfigFactory
) -> None:
    first_session = build_session_factory(f"sqlite:///{(tmp_path / 'a.db').as_posix()}")()
    second_session = build_session_factory(f"sqlite:///{(tmp_path / 'b.db').as_posix()}")()

    create_server(first_session, stdio_config_factory(name="only-in-first"))

    assert [server.name for server in list_servers(first_session)] == ["only-in-first"]
    assert list_servers(second_session) == []
