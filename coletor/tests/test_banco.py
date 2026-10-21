"""Phase 1 checks: seed data, least-privilege permissions, idempotency, views.

All writes happen inside transactions that are rolled back.
"""

from typing import LiteralString, cast

import psycopg
import pytest

from tests.conftest import Connect

MANAUS = "14990000"


def fetch_one(conn: psycopg.Connection, sql: LiteralString) -> tuple:
    row = conn.execute(sql).fetchone()
    assert row is not None
    return row


def assert_denied(connect: Connect, user: str, sql: str) -> None:
    conn = connect(user)
    with pytest.raises(psycopg.errors.InsufficientPrivilege):
        conn.execute(cast(LiteralString, sql))


def new_collection(conn: psycopg.Connection) -> int:
    return fetch_one(
        conn, "INSERT INTO dados.coletas (fonte) VALUES ('ana_telemetria') RETURNING id"
    )[0]


# ---------------------------------------------------------------- seed


def test_seed_has_4_rivers_and_10_stations(connect: Connect) -> None:
    conn = connect("rios_leitura")
    assert fetch_one(conn, "SELECT count(DISTINCT rio) FROM analise.estacoes")[0] == 4
    assert fetch_one(conn, "SELECT count(*) FROM analise.estacoes")[0] == 10


def test_manaus_reference_levels(connect: Connect) -> None:
    conn = connect("rios_leitura")
    rows = conn.execute(
        "SELECT tipo, cota_cm FROM analise.cotas_vigentes WHERE estacao = %s", (MANAUS,)
    ).fetchall()
    cotas = {tipo: float(cota) for tipo, cota in rows}
    assert cotas["alerta"] == 2700
    assert cotas["inundacao"] == 2750
    assert cotas["inundacao_severa"] == 2900
    assert cotas["minima_historica"] == 1213


# ---------------------------------------------------------------- rios_coletor


def test_collector_writes_readings(connect: Connect) -> None:
    conn = connect("rios_coletor")
    coleta = new_collection(conn)
    conn.execute(
        "INSERT INTO bruto.respostas (coleta_id, fonte, url) VALUES (%s, 'ana_telemetria', 'x')",
        (coleta,),
    )
    conn.execute(
        "INSERT INTO dados.leituras (estacao, instante, fonte, cota_cm, coleta_id) "
        "VALUES (%s, now(), 'ana_telemetria', 1703, %s)",
        (MANAUS, coleta),
    )


def test_upsert_is_idempotent(connect: Connect) -> None:
    conn = connect("rios_coletor")
    coleta = new_collection(conn)
    upsert = (
        "INSERT INTO dados.leituras (estacao, instante, fonte, cota_cm, coleta_id) "
        "VALUES (%s, '2026-10-20 12:00-04', 'ana_telemetria', %s, %s) "
        "ON CONFLICT (estacao, instante, fonte) DO UPDATE SET cota_cm = EXCLUDED.cota_cm"
    )
    for cota in (1703, 1703, 1704):
        conn.execute(upsert, (MANAUS, cota, coleta))
    count, cota = fetch_one(
        conn,
        "SELECT count(*), max(cota_cm) FROM dados.leituras "
        f"WHERE estacao = '{MANAUS}' AND instante = '2026-10-20 12:00-04'",
    )
    assert count == 1
    assert cota == 1704


def test_suspect_reading_requires_reason(connect: Connect) -> None:
    conn = connect("rios_coletor")
    with pytest.raises(psycopg.errors.CheckViolation):
        conn.execute(
            "INSERT INTO dados.leituras (estacao, instante, fonte, cota_cm, qualidade) "
            f"VALUES ('{MANAUS}', now(), 'porto_manaus', 2012, 'suspeita')"
        )


@pytest.mark.parametrize(
    "sql",
    [
        "SELECT * FROM dados.inscritos",
        "UPDATE dados.estacoes SET ativa = false",
        "DELETE FROM dados.leituras",
        "INSERT INTO dados.cotas_referencia VALUES ('14990000', 'alerta', 1, NULL, 'x', now())",
        "CREATE TABLE dados.intrusa (x int)",
        "CREATE TABLE public.intrusa (x int)",
    ],
)
def test_collector_denied(connect: Connect, sql: str) -> None:
    assert_denied(connect, "rios_coletor", sql)


# ---------------------------------------------------------------- rios_n8n


def test_n8n_reads_views_and_manages_subscribers(connect: Connect) -> None:
    conn = connect("rios_n8n")
    conn.execute("SELECT * FROM analise.situacao_estacao").fetchall()
    conn.execute(
        "INSERT INTO dados.inscritos (chat_id, estacoes) VALUES (-1, ARRAY[%s])", (MANAUS,)
    )
    conn.execute(
        'UPDATE dados.inscritos SET ultimos_alertas = \'{"14990000": "alerta"}\' WHERE chat_id = -1'
    )


@pytest.mark.parametrize(
    "sql",
    [
        "SELECT * FROM dados.leituras",
        "SELECT * FROM bruto.respostas",
        "INSERT INTO dados.coletas (fonte) VALUES ('ana_telemetria')",
        "DELETE FROM dados.inscritos",
        "CREATE TABLE analise.intrusa (x int)",
    ],
)
def test_n8n_denied(connect: Connect, sql: str) -> None:
    assert_denied(connect, "rios_n8n", sql)


# ---------------------------------------------------------------- rios_leitura


def test_reader_reads_all_views(connect: Connect) -> None:
    conn = connect("rios_leitura")
    for view in (
        "estacoes",
        "cotas_vigentes",
        "ultima_leitura",
        "leituras_diarias",
        "situacao_estacao",
        "comparativo_anual",
    ):
        conn.execute(f"SELECT * FROM analise.{view} LIMIT 1").fetchall()


@pytest.mark.parametrize(
    "sql",
    [
        "SELECT * FROM dados.leituras",
        "SELECT * FROM dados.inscritos",
        "SELECT * FROM bruto.respostas",
        "INSERT INTO dados.inscritos (chat_id) VALUES (-1)",
    ],
)
def test_reader_denied(connect: Connect, sql: str) -> None:
    assert_denied(connect, "rios_leitura", sql)


# ---------------------------------------------------------------- views


@pytest.mark.parametrize(
    ("cota", "situacao"),
    [
        (1703, "normal"),
        (2710, "alerta"),
        (2760, "inundacao"),
        (2950, "inundacao_severa"),
    ],
)
def test_manaus_situation(connect: Connect, cota: int, situacao: str) -> None:
    conn = connect("rios_coletor")
    coleta = new_collection(conn)
    conn.execute(
        "INSERT INTO dados.leituras (estacao, instante, fonte, cota_cm, coleta_id) "
        "VALUES (%s, now() + interval '1 day', 'ana_telemetria', %s, %s)",
        (MANAUS, cota, coleta),
    )
    row = conn.execute(
        "SELECT situacao FROM analise.situacao_estacao WHERE codigo_ana = %s", (MANAUS,)
    ).fetchone()
    assert row == (situacao,)


def test_suspect_reading_is_hidden_from_views(connect: Connect) -> None:
    conn = connect("rios_coletor")
    coleta = new_collection(conn)
    conn.execute(
        "INSERT INTO dados.leituras "
        "(estacao, instante, fonte, cota_cm, qualidade, motivo, coleta_id) "
        "VALUES (%s, now() + interval '2 days', 'porto_manaus', 2012, 'suspeita', "
        "'salto brusco', %s)",
        (MANAUS, coleta),
    )
    row = conn.execute(
        "SELECT cota_cm FROM analise.ultima_leitura WHERE codigo_ana = %s", (MANAUS,)
    ).fetchone()
    assert row is None or row[0] != 2012


def test_station_without_levels_has_no_reference(connect: Connect) -> None:
    conn = connect("rios_coletor")
    coleta = new_collection(conn)
    conn.execute(
        "INSERT INTO dados.leituras (estacao, instante, fonte, cota_cm, coleta_id) "
        "VALUES ('14480002', now() + interval '1 day', 'ana_telemetria', 500, %s)",
        (coleta,),
    )
    row = conn.execute(
        "SELECT situacao FROM analise.situacao_estacao WHERE codigo_ana = '14480002'"
    ).fetchone()
    assert row == ("sem_referencia",)
