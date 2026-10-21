"""Phase 4: collection runs end to end against the real database, with fake HTTP.

Commits are disabled and everything is rolled back, so the database stays clean.
"""

import gzip
from datetime import UTC, date, datetime, timedelta
from pathlib import Path

import httpx
import psycopg
import pytest

from rios import coleta
from rios.banco import Estacao, apagar_brutos_antigos, iniciar_coleta, salvar_resposta
from rios.fontes import porto
from rios.fontes.http import Resposta
from tests.conftest import Connect

FIXTURES = Path(__file__).parent / "fixtures"
# Real captures moved to 1990 so they never collide with collected data in the database
ANA_XML = (FIXTURES / "ana_14990000_2026-10-20.xml").read_bytes().replace(b"2026-", b"1990-")
PORTO_HTML = (FIXTURES / "porto_manaus_2026-10-20.html").read_bytes().replace(b" 2026", b" 1990")
DIA = date(1990, 10, 20)
MANAUS = Estacao("14990000", "Manaus", "Negro", 3)
BARCELOS = Estacao("14480002", "Barcelos", "Negro", 2)


def cliente_falso(respostas: dict[str, tuple[int, bytes]]) -> httpx.Client:
    """Answer by URL substring; anything unknown is a 504."""

    def responder(request: httpx.Request) -> httpx.Response:
        for trecho, (status, corpo) in respostas.items():
            if trecho in str(request.url):
                return httpx.Response(status, content=corpo)
        return httpx.Response(504, content=b"<html>504 Gateway Time-out</html>")

    return httpx.Client(transport=httpx.MockTransport(responder))


@pytest.fixture
def conn(connect: Connect, monkeypatch: pytest.MonkeyPatch) -> psycopg.Connection:
    conexao = connect("rios_coletor")
    monkeypatch.setattr(conexao, "commit", lambda: None)
    return conexao


def contar(conn: psycopg.Connection, coleta_id: int | None) -> tuple[int, int]:
    linha = conn.execute(
        "SELECT (SELECT count(*) FROM dados.leituras WHERE coleta_id = %s), "
        "(SELECT count(*) FROM bruto.respostas WHERE coleta_id = %s)",
        (coleta_id, coleta_id),
    ).fetchone()
    assert linha is not None
    return linha


def status_coleta(conn: psycopg.Connection, coleta_id: int | None) -> tuple:
    linha = conn.execute(
        "SELECT status, leituras_novas, erro IS NOT NULL, fim IS NOT NULL "
        "FROM dados.coletas WHERE id = %s",
        (coleta_id,),
    ).fetchone()
    assert linha is not None
    return linha


def test_periods_split_long_ranges() -> None:
    assert coleta.periodos(date(2026, 1, 1), date(2026, 1, 1)) == [
        (date(2026, 1, 1), date(2026, 1, 1))
    ]
    partes = coleta.periodos(date(2024, 1, 1), date(2024, 12, 31))
    assert partes[0] == (date(2024, 1, 1), date(2024, 1, 31))
    assert partes[-1][1] == date(2024, 12, 31)
    assert all(fim >= inicio for inicio, fim in partes)
    assert sum((fim - inicio).days + 1 for inicio, fim in partes) == 366


def test_ana_run_writes_raw_and_clean_layers(conn: psycopg.Connection) -> None:
    cliente = cliente_falso({"14990000": (200, ANA_XML)})
    resultado = coleta.coletar_ana(cliente, [MANAUS], DIA, DIA, conn=conn)
    assert resultado.status == "sucesso"
    assert resultado.leituras_novas == 88
    assert contar(conn, resultado.coleta_id) == (88, 1)
    assert status_coleta(conn, resultado.coleta_id) == ("sucesso", 88, False, True)
    conteudo = conn.execute(
        "SELECT conteudo FROM bruto.respostas WHERE coleta_id = %s", (resultado.coleta_id,)
    ).fetchone()
    assert conteudo is not None and gzip.decompress(conteudo[0]) == ANA_XML


def test_ana_run_is_idempotent(conn: psycopg.Connection) -> None:
    cliente = cliente_falso({"14990000": (200, ANA_XML)})
    args = (cliente, [MANAUS], DIA, DIA)
    primeira = coleta.coletar_ana(*args, conn=conn)
    segunda = coleta.coletar_ana(*args, conn=conn)
    assert primeira.leituras_novas == 88
    assert segunda.leituras_novas == 0
    total = conn.execute(
        "SELECT count(*) FROM dados.leituras WHERE estacao = '14990000' "
        "AND fonte = 'ana_telemetria' "
        "AND instante >= '1990-10-20 00:00-03' AND instante < '1990-10-21 00:00-03'"
    ).fetchone()
    assert total == (88,)


def test_one_station_failing_makes_run_partial(conn: psycopg.Connection) -> None:
    cliente = cliente_falso({"14990000": (200, ANA_XML)})  # Barcelos gets 504
    resultado = coleta.coletar_ana(cliente, [BARCELOS, MANAUS], DIA, DIA, conn=conn)
    assert resultado.status == "parcial"
    assert resultado.leituras_novas == 88
    assert status_coleta(conn, resultado.coleta_id)[0:3] == ("parcial", 88, True)
    # the 504 page is kept in the raw layer for auditing
    assert contar(conn, resultado.coleta_id) == (88, 2)


def test_all_failing_is_a_failed_run(conn: psycopg.Connection) -> None:
    resultado = coleta.coletar_ana(cliente_falso({}), [MANAUS], DIA, DIA, conn=conn)
    assert resultado.status == "falha"
    assert status_coleta(conn, resultado.coleta_id)[0] == "falha"


def test_porto_run_writes_corrected_values(conn: psycopg.Connection) -> None:
    cliente = cliente_falso({"portodemanaus": (200, PORTO_HTML)})
    resultado = coleta.coletar_porto(cliente, conn=conn)
    assert resultado.status == "sucesso"
    assert resultado.leituras_novas == 173
    linha = conn.execute(
        "SELECT cota_cm, cota_original, qualidade FROM dados.leituras "
        "WHERE fonte = 'porto_manaus' AND instante = '1990-06-06 00:00-04'"
    ).fetchone()
    assert linha == (2812, "20.12", "corrigida")


def test_porto_layout_change_is_a_failed_run(conn: psycopg.Connection) -> None:
    cliente = cliente_falso({"portodemanaus": (200, b"<html>novo layout</html>")})
    resultado = coleta.coletar_porto(cliente, conn=conn)
    assert resultado.status == "falha"
    assert "tabela" in resultado.falhas[0] or "table" in resultado.falhas[0]


def test_preview_without_connection_writes_nothing() -> None:
    cliente = cliente_falso({"portodemanaus": (200, PORTO_HTML)})
    resultado = coleta.coletar_porto(cliente)
    assert resultado.coleta_id is None
    assert len(resultado.leituras) == 173


def test_old_raw_responses_are_pruned(conn: psycopg.Connection) -> None:
    coleta_id = iniciar_coleta(conn, "ana_telemetria")
    antiga = Resposta("https://x", 200, b"<xml/>", datetime.now(UTC) - timedelta(days=91))
    salvar_resposta(conn, coleta_id, "ana_telemetria", antiga)
    assert apagar_brutos_antigos(conn, dias=90) >= 1
    assert contar(conn, coleta_id)[1] == 0


def test_porto_url_constant() -> None:
    assert porto.URL.startswith("https://portodemanaus.com.br/")
