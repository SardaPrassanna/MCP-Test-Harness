from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Literal

import yaml
from pydantic import ValidationError

from mcp_test_harness.models.scenario import TestScenario

ScenarioFormat = Literal["yaml", "json"]

_FORMAT_BY_SUFFIX: dict[str, ScenarioFormat] = {
    ".yaml": "yaml",
    ".yml": "yaml",
    ".json": "json",
}


class ScenarioLoadError(Exception):
    """Raised when scenario source text or a scenario file cannot be parsed
    or fails scenario validation. The message always says which scenario
    (and, when loading from a file, which file) is at fault."""


def load_scenarios_from_text(text: str, *, format: ScenarioFormat) -> list[TestScenario]:
    """Parse and validate scenarios from a YAML or JSON string.

    Accepts either a single scenario mapping or a list of scenario
    mappings. Raises `ScenarioLoadError` with a clear, per-scenario message
    on a syntax error or a scenario that fails validation.
    """
    try:
        data: Any = yaml.safe_load(text) if format == "yaml" else json.loads(text)
    except (yaml.YAMLError, json.JSONDecodeError) as exc:
        raise ScenarioLoadError(f"could not parse scenario {format.upper()}: {exc}") from exc

    if data is None:
        raise ScenarioLoadError("scenario source is empty")

    raw_scenarios: list[Any] = data if isinstance(data, list) else [data]
    if not raw_scenarios:
        raise ScenarioLoadError("scenario source contains no scenarios")

    scenarios: list[TestScenario] = []
    for index, raw_scenario in enumerate(raw_scenarios):
        position = f"scenario #{index + 1}"
        if not isinstance(raw_scenario, dict):
            raise ScenarioLoadError(
                f"{position} must be a mapping, got {type(raw_scenario).__name__}"
            )
        try:
            scenarios.append(TestScenario.model_validate(raw_scenario))
        except ValidationError as exc:
            scenario_name = raw_scenario.get("name", "<unnamed>")
            raise ScenarioLoadError(f"{position} ({scenario_name!r}) is invalid: {exc}") from exc

    return scenarios


def load_scenarios_from_file(path: str | Path) -> list[TestScenario]:
    """Load and validate scenarios from a `.yaml`, `.yml`, or `.json` file."""
    file_path = Path(path)
    scenario_format = _FORMAT_BY_SUFFIX.get(file_path.suffix.lower())
    if scenario_format is None:
        raise ScenarioLoadError(
            f"unsupported scenario file extension {file_path.suffix!r} in {file_path}; "
            "use .yaml, .yml, or .json"
        )

    try:
        text = file_path.read_text(encoding="utf-8")
    except OSError as exc:
        raise ScenarioLoadError(f"could not read scenario file {file_path}: {exc}") from exc

    try:
        return load_scenarios_from_text(text, format=scenario_format)
    except ScenarioLoadError as exc:
        raise ScenarioLoadError(f"{file_path}: {exc}") from exc
