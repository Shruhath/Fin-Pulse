"""Shared fixtures.

Database tests run against a scratch database (`finpulse_test`) that is dropped, created and
migrated once per session, so they exercise the real Alembic schema and never touch the
development data. They need the PostgreSQL service from infra/docker-compose.yml; when it is
not reachable they fail loudly rather than skip, so a green run always means they ran.
"""

from __future__ import annotations

import os
from collections.abc import Iterator
from pathlib import Path

import pytest
from sqlalchemy import create_engine, text
from sqlalchemy.engine import make_url
from sqlalchemy.orm import Session

TEST_DB_URL = os.environ.get(
    "FINPULSE_TEST_DATABASE_URL",
    "postgresql+psycopg://finpulse:finpulse@127.0.0.1:5433/finpulse_test",
)
# Settings are read lazily, so pointing them at the scratch database here is enough.
os.environ["FINPULSE_DATABASE_URL"] = TEST_DB_URL

SERVER_DIR = Path(__file__).resolve().parents[1]


@pytest.fixture(scope="session")
def migrated_db() -> str:
    from alembic import command
    from alembic.config import Config

    url = make_url(TEST_DB_URL)
    admin = create_engine(url.set(database="postgres"), isolation_level="AUTOCOMMIT")
    with admin.connect() as conn:
        conn.execute(text(f'DROP DATABASE IF EXISTS "{url.database}" WITH (FORCE)'))
        conn.execute(text(f'CREATE DATABASE "{url.database}"'))
    admin.dispose()

    cfg = Config(str(SERVER_DIR / "alembic.ini"))
    cfg.set_main_option("script_location", str(SERVER_DIR / "alembic"))
    command.upgrade(cfg, "head")
    return TEST_DB_URL


@pytest.fixture
def db(migrated_db: str) -> Iterator[Session]:
    """A session whose work is rolled back, so tests stay independent."""
    from finpulse.db.session import get_engine

    connection = get_engine().connect()
    outer = connection.begin()
    session = Session(bind=connection, join_transaction_mode="create_savepoint", expire_on_commit=False)
    try:
        yield session
    finally:
        session.close()
        outer.rollback()
        connection.close()


@pytest.fixture
def client(db: Session) -> Iterator[object]:
    """The real FastAPI app, reading and writing through the test's rolled-back session."""
    from fastapi.testclient import TestClient

    from finpulse.api.app import app
    from finpulse.api.deps import get_db

    app.dependency_overrides[get_db] = lambda: db
    try:
        yield TestClient(app)
    finally:
        app.dependency_overrides.clear()
