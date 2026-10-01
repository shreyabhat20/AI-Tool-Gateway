import os

import pytest
from alembic import command
from alembic.config import Config
from sqlalchemy import create_engine, inspect

from app.core.config import get_settings


@pytest.mark.skipif(not os.getenv("TEST_DATABASE_URL"), reason="Set TEST_DATABASE_URL to an isolated PostgreSQL test database")
def test_initial_migration(monkeypatch: pytest.MonkeyPatch) -> None:
    url = os.environ["TEST_DATABASE_URL"]
    assert "test" in url.rsplit("/", 1)[-1], "Migration test requires a disposable test database"
    monkeypatch.setenv("DATABASE_URL", url)
    get_settings.cache_clear()
    config = Config("alembic.ini")
    command.upgrade(config, "head")
    engine = create_engine(url)
    try:
        tables = set(inspect(engine).get_table_names())
        assert {"users", "tools", "tool_permissions", "tool_invocations"} <= tables
    finally:
        engine.dispose()
        command.downgrade(config, "base")
        get_settings.cache_clear()

