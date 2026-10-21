"""Database access for the collector (user rios_coletor)."""

import gzip
from collections.abc import Iterable
from dataclasses import dataclass
from decimal import Decimal

import psycopg

from rios.config import dsn
from rios.fontes.http import Resposta
from rios.limpeza import LeituraLimpa


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


# ---------------------------------------------------------------- writes (Phase 4)

VERSAO_PARSER = "0.1.0"


def iniciar_coleta(conn: psycopg.Connection, fonte: str) -> int:
    linha = conn.execute(
        "INSERT INTO dados.coletas (fonte) VALUES (%s) RETURNING id", (fonte,)
    ).fetchone()
    assert linha is not None
    conn.commit()
    return linha[0]


def salvar_resposta(
    conn: psycopg.Connection, coleta_id: int, fonte: str, resposta: Resposta
) -> None:
    """Keep the original response (gzip) in the raw layer."""
    conn.execute(
        "INSERT INTO bruto.respostas "
        "(coleta_id, fonte, url, recebido_em, status_http, conteudo, versao_parser) "
        "VALUES (%s, %s, %s, %s, %s, %s, %s)",
        (
            coleta_id,
            fonte,
            resposta.url,
            resposta.recebido_em,
            resposta.status_http,
            gzip.compress(resposta.conteudo),
            VERSAO_PARSER,
        ),
    )


def gravar_leituras(
    conn: psycopg.Connection, coleta_id: int, leituras: Iterable[LeituraLimpa]
) -> int:
    """Upsert readings. Returns how many rows were inserted or actually changed."""
    sql = """
        INSERT INTO dados.leituras
            (estacao, instante, fonte, cota_cm, cota_original, qualidade, motivo, coleta_id)
        VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
        ON CONFLICT (estacao, instante, fonte) DO UPDATE SET
            cota_cm = EXCLUDED.cota_cm,
            cota_original = EXCLUDED.cota_original,
            qualidade = EXCLUDED.qualidade,
            motivo = EXCLUDED.motivo,
            coleta_id = EXCLUDED.coleta_id,
            atualizado_em = now()
        WHERE (dados.leituras.cota_cm, dados.leituras.cota_original,
               dados.leituras.qualidade, dados.leituras.motivo)
              IS DISTINCT FROM
              (EXCLUDED.cota_cm, EXCLUDED.cota_original, EXCLUDED.qualidade, EXCLUDED.motivo)
    """
    linhas = [
        (
            leitura.estacao,
            leitura.instante,
            leitura.fonte,
            leitura.cota_cm,
            leitura.cota_original,
            leitura.qualidade,
            leitura.motivo,
            coleta_id,
        )
        for leitura in leituras
    ]
    with conn.cursor() as cur:
        cur.executemany(sql, linhas, returning=False)
        return max(cur.rowcount, 0)


def finalizar_coleta(
    conn: psycopg.Connection, coleta_id: int, status: str, leituras_novas: int, erro: str | None
) -> None:
    conn.execute(
        "UPDATE dados.coletas SET fim = now(), status = %s, leituras_novas = %s, erro = %s "
        "WHERE id = %s",
        (status, leituras_novas, erro, coleta_id),
    )
    conn.commit()


def apagar_brutos_antigos(conn: psycopg.Connection, dias: int = 90) -> int:
    cur = conn.execute(
        "DELETE FROM bruto.respostas WHERE recebido_em < now() - make_interval(days => %s)",
        (dias,),
    )
    conn.commit()
    return cur.rowcount
