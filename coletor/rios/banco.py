"""Database access for the collector (user rios_coletor)."""

from dataclasses import dataclass
from decimal import Decimal

import psycopg

from rios.config import dsn


@dataclass(frozen=True)
class Estacao:
    codigo_ana: str
    nome: str
    rio: str
    ordem_no_rio: int


def conectar_coletor() -> psycopg.Connection:
    return psycopg.connect(dsn("rios_coletor", "RIOS_COLETOR_PASSWORD"))


def estacoes_ativas(conn: psycopg.Connection) -> list[Estacao]:
    linhas = conn.execute(
        "SELECT codigo_ana, nome, rio, ordem_no_rio FROM analise.estacoes "
        "WHERE ativa ORDER BY rio, ordem_no_rio"
    ).fetchall()
    return [Estacao(*linha) for linha in linhas]


def faixas_historicas(conn: psycopg.Connection) -> dict[str, tuple[Decimal, Decimal]]:
    """Historical (min, max) level per station, in cm, from the reference levels."""
    linhas = conn.execute(
        "SELECT estacao, "
        "max(cota_cm) FILTER (WHERE tipo = 'minima_historica'), "
        "max(cota_cm) FILTER (WHERE tipo = 'maxima_historica') "
        "FROM analise.cotas_vigentes GROUP BY estacao"
    ).fetchall()
    return {
        estacao: (minima, maxima)
        for estacao, minima, maxima in linhas
        if minima is not None and maxima is not None
    }
