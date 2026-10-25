"""Shared fixtures: database connections for each service user."""

from collections.abc import Callable, Iterator

import psycopg
import pytest

from rios.config import ENV_FILE, carregar_env

USERS = {
    "rios_coletor": "RIOS_COLETOR_PASSWORD",
    "rios_n8n": "RIOS_N8N_PASSWORD",
    "rios_leitura": "RIOS_LEITURA_PASSWORD",
}


@pytest.fixture(scope="session")
def env() -> dict[str, str]:
    """Settings from .env or RIOS_* environment variables (used in CI)."""
    env = carregar_env(ENV_FILE)
    if "RIOS_DB_HOST" not in env:
        pytest.skip(f"no database configured ({ENV_FILE} or RIOS_* variables)")
    return env


Connect = Callable[[str], psycopg.Connection]


@pytest.fixture
def connect(env: dict[str, str]) -> Iterator[Connect]:
    """Open a connection as the given user. Everything is rolled back at the end."""
    opened: list[psycopg.Connection] = []

    def _connect(user: str) -> psycopg.Connection:
        conn = psycopg.connect(
            host=env["RIOS_DB_HOST"],
            port=env["RIOS_DB_PORT"],
            dbname=env["RIOS_DB_NAME"],
            user=user,
            password=env[USERS[user]],
        )
        opened.append(conn)
        return conn

    yield _connect
    for conn in opened:
        conn.rollback()
        conn.close()
