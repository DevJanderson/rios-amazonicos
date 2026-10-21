"""Settings from the project's .env (one level above coletor/) or the environment."""

import os
from pathlib import Path

ENV_FILE = Path(__file__).resolve().parents[2] / ".env"


def carregar_env(path: Path = ENV_FILE) -> dict[str, str]:
    env: dict[str, str] = {}
    if path.exists():
        for linha in path.read_text().splitlines():
            linha = linha.strip()
            if linha and not linha.startswith("#") and "=" in linha:
                chave, valor = linha.split("=", 1)
                env[chave] = valor
    env.update({k: v for k, v in os.environ.items() if k.startswith("RIOS_")})
    return env


def dsn(usuario: str, senha_var: str, env: dict[str, str] | None = None) -> str:
    env = carregar_env() if env is None else env
    return (
        f"host={env['RIOS_DB_HOST']} port={env['RIOS_DB_PORT']} dbname={env['RIOS_DB_NAME']} "
        f"user={usuario} password={env[senha_var]}"
    )
