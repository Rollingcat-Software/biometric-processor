"""Offline rendering of the whole alembic chain (issue #189).

``alembic upgrade head --sql`` builds every migration into a SQL script
without a database. It catches, without any infrastructure:

* a model module that cannot be imported by ``alembic/env.py``;
* a column type that cannot be compiled (an ENUM without a type name);
* a migration that touches a table no earlier migration created, which is
  what an empty database hits first.

The live counterpart, which runs the chain against an empty pgvector
database, is ``tests/integration/persistence/test_alembic_empty_database.py``.
"""

import io
import re
from pathlib import Path

import pytest
from alembic import command
from alembic.config import Config
from alembic.script import ScriptDirectory

REPO_ROOT = Path(__file__).resolve().parents[4]

# Statements that require the table to exist already.
_TABLE_USE = re.compile(
    r"\b(?:ALTER TABLE|ANALYZE|INSERT INTO|UPDATE|ON)\s+(?:ONLY\s+)?([a-z_][a-z0-9_]*)\b",
    re.IGNORECASE,
)
_TABLE_CREATE = re.compile(
    r"\bCREATE TABLE\s+(?:IF NOT EXISTS\s+)?([a-z_][a-z0-9_]*)\b", re.IGNORECASE
)
_NOT_TABLES = {"conflict", "delete", "update", "commit"}


def _alembic_config(**kwargs) -> Config:
    # No ini file on purpose: alembic/env.py calls logging.config.fileConfig()
    # when the config has a file name, which disables every existing logger
    # and breaks caplog assertions in tests that run later in the session.
    config = Config(**kwargs)
    config.set_main_option("script_location", str(REPO_ROOT / "alembic"))
    return config


@pytest.fixture(scope="module")
def upgrade_sql(monkeypatch_module) -> str:
    monkeypatch_module.setenv(
        "DATABASE_URL", "postgresql+asyncpg://offline:offline@localhost:5432/offline"
    )
    buffer = io.StringIO()
    command.upgrade(_alembic_config(output_buffer=buffer), "head", sql=True)
    return buffer.getvalue()


@pytest.fixture(scope="module")
def monkeypatch_module():
    patcher = pytest.MonkeyPatch()
    yield patcher
    patcher.undo()


def test_upgrade_WhenRenderedOffline_ShouldNameEverySessionEnumType(
    upgrade_sql: str,
) -> None:
    assert re.search(r"\n\s+status session_status\b", upgrade_sql)
    assert re.search(r"\n\s+incident_type incident_type\b", upgrade_sql)
    assert re.search(r"\n\s+severity incident_severity\b", upgrade_sql)
    assert re.search(r"\n\s+review_action review_action\b", upgrade_sql)


def test_upgrade_WhenRenderedOfflineFromEmptyDatabase_ShouldCreateEveryTableBeforeUsingIt(
    upgrade_sql: str,
) -> None:
    created: set[str] = set()
    used_before_created: list[str] = []
    for statement in upgrade_sql.split(";"):
        for match in _TABLE_CREATE.finditer(statement):
            created.add(match.group(1).lower())
        for match in _TABLE_USE.finditer(statement):
            table = match.group(1).lower()
            if table in _NOT_TABLES or table in created:
                continue
            used_before_created.append(f"{table}: {statement.strip()[:120]}")

    assert not used_before_created, "\n".join(used_before_created)


def test_upgrade_WhenRevisionIdExceedsVersionColumn_ShouldWidenColumnBeforeStamping(
    upgrade_sql: str,
) -> None:
    created_width = int(
        re.search(
            r"CREATE TABLE alembic_version \(\s*version_num VARCHAR\((\d+)\)",
            upgrade_sql,
        ).group(1)
    )
    widenings = [
        (match.start(), int(match.group(1)))
        for match in re.finditer(
            r"ALTER TABLE alembic_version ALTER COLUMN version_num TYPE VARCHAR\((\d+)\)",
            upgrade_sql,
        )
    ]
    problems = []
    for stamp in re.finditer(r"version_num='([^']+)'", upgrade_sql):
        revision = stamp.group(1)
        width = max(
            [created_width] + [w for pos, w in widenings if pos < stamp.start()]
        )
        if len(revision) > width:
            problems.append(f"{revision} ({len(revision)} chars) > VARCHAR({width})")

    assert not problems, problems


def test_upgrade_WhenRenderedOffline_ShouldStampTheSingleHeadRevision(
    upgrade_sql: str,
) -> None:
    head = ScriptDirectory.from_config(_alembic_config()).get_current_head()

    assert f"UPDATE alembic_version SET version_num='{head}'" in upgrade_sql
