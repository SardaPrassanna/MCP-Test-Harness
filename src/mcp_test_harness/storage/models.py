from __future__ import annotations

from datetime import UTC, datetime
from typing import Any, ClassVar

from sqlalchemy import JSON, DateTime, ForeignKey, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from mcp_test_harness.storage.database import Base


def _utcnow() -> datetime:
    return datetime.now(UTC)


class ServerRecord(Base):
    """A registered MCP server's connection config, as submitted to `POST /servers`."""

    __tablename__ = "servers"
    __test__: ClassVar[bool] = False  # not a pytest test class despite the name

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String, unique=True, index=True)
    transport: Mapped[str] = mapped_column(String)
    config: Mapped[dict[str, Any]] = mapped_column(JSON)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow)


class ScenarioRecord(Base):
    """A registered declarative test scenario, as submitted to `POST /tests`."""

    __tablename__ = "scenarios"
    __test__: ClassVar[bool] = False  # not a pytest test class despite the name

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String, index=True)
    server: Mapped[str] = mapped_column(String, index=True)
    tool: Mapped[str] = mapped_column(String)
    input: Mapped[dict[str, Any]] = mapped_column(JSON)
    assertions: Mapped[dict[str, Any]] = mapped_column(JSON)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow)


class TestRunRecord(Base):
    """One execution of a batch of scenarios, with aggregated pass/fail/error counts."""

    __tablename__ = "test_runs"
    __test__: ClassVar[bool] = False  # not a pytest test class despite the name

    id: Mapped[int] = mapped_column(primary_key=True)
    status: Mapped[str] = mapped_column(String)
    passed: Mapped[int] = mapped_column(default=0)
    failed: Mapped[int] = mapped_column(default=0)
    errored: Mapped[int] = mapped_column(default=0)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow)

    results: Mapped[list[TestResultRecord]] = relationship(
        back_populates="run", cascade="all, delete-orphan", order_by="TestResultRecord.id"
    )


class TestResultRecord(Base):
    """One scenario's outcome within a `TestRunRecord`."""

    __tablename__ = "test_results"
    __test__: ClassVar[bool] = False  # not a pytest test class despite the name

    id: Mapped[int] = mapped_column(primary_key=True)
    run_id: Mapped[int] = mapped_column(ForeignKey("test_runs.id"))
    scenario: Mapped[str] = mapped_column(String)
    server: Mapped[str] = mapped_column(String)
    tool: Mapped[str] = mapped_column(String)
    status: Mapped[str] = mapped_column(String)
    duration_seconds: Mapped[float] = mapped_column()
    assertions: Mapped[list[dict[str, Any]]] = mapped_column(JSON, default=list)
    error: Mapped[str | None] = mapped_column(Text, nullable=True)
    response: Mapped[dict[str, Any] | None] = mapped_column(JSON, nullable=True)

    run: Mapped[TestRunRecord] = relationship(back_populates="results")
