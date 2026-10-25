"""Phase 5: Telegram bot logic in the database (schema ``bot``), run as rios_n8n.

Fake chat ids are negative so they never clash with real subscribers; everything
is rolled back at the end.
"""

import psycopg
import pytest

from tests.conftest import Connect

CHAT = -1
MANAUS = "14990000"


@pytest.fixture
def n8n(connect: Connect) -> psycopg.Connection:
    return connect("rios_n8n")


def responder(conn: psycopg.Connection, texto: str, chat: int = CHAT) -> str:
    linha = conn.execute("SELECT bot.responder(%s, %s)", (chat, texto)).fetchone()
    assert linha is not None and linha[0] is not None
    return linha[0]


def inscrito(conn: psycopg.Connection, chat: int = CHAT) -> tuple:
    linha = conn.execute(
        "SELECT ativo, estacoes, ultimos_alertas FROM dados.inscritos WHERE chat_id = %s", (chat,)
    ).fetchone()
    assert linha is not None
    return linha


def pendentes(conn: psycopg.Connection, chat: int = CHAT) -> list[tuple]:
    return conn.execute(
        "SELECT estacao, situacao, mensagem FROM bot.alertas_pendentes() WHERE chat_id = %s",
        (chat,),
    ).fetchall()


@pytest.mark.parametrize("texto", ["manaus", "MANAUS", "  Manaus ", "14990000", "man"])
def test_station_lookup_is_forgiving(n8n: psycopg.Connection, texto: str) -> None:
    assert n8n.execute("SELECT bot.buscar_estacao(%s)", (texto,)).fetchone() == (MANAUS,)


@pytest.mark.parametrize(
    ("texto", "codigo"),
    [
        ("humaita", "15630000"),
        ("São Gabriel", "14320001"),
        ("sao gabriel", "14320001"),
        ("coari", "13150000"),
        ("porto velho", "15400000"),
    ],
)
def test_station_lookup_ignores_accents(n8n: psycopg.Connection, texto: str, codigo: str) -> None:
    assert n8n.execute("SELECT bot.buscar_estacao(%s)", (texto,)).fetchone() == (codigo,)


def test_start_subscribes_and_stop_unsubscribes(n8n: psycopg.Connection) -> None:
    assert "/nivel" in responder(n8n, "/start")
    assert inscrito(n8n) == (True, [], {})
    assert "cancelada" in responder(n8n, "/parar")
    assert inscrito(n8n)[0] is False
    responder(n8n, "/start")
    assert inscrito(n8n)[0] is True


def test_level_reply(n8n: psycopg.Connection) -> None:
    texto = responder(n8n, "/nivel manaus")
    assert texto.startswith("Manaus (rio Negro)")
    assert " m em " in texto and "24 h" in texto


def test_command_with_bot_username(n8n: psycopg.Connection) -> None:
    assert responder(n8n, "/nivel@rios_amazonicos_bot manaus").startswith("Manaus")


def test_unknown_city_lists_stations(n8n: psycopg.Connection) -> None:
    texto = responder(n8n, "/nivel atlantida")
    assert "Não encontrei" in texto and "Parintins" in texto


def test_missing_city_asks_for_it(n8n: psycopg.Connection) -> None:
    assert "Exemplo: /semana manaus" in responder(n8n, "/semana")


def test_week_reply_has_one_line_per_day(n8n: psycopg.Connection) -> None:
    linhas = responder(n8n, "/semana manaus").splitlines()
    assert linhas[0] == "Manaus — últimos 7 dias"
    assert 1 <= len(linhas) - 1 <= 7


def test_stale_station_is_flagged(n8n: psycopg.Connection) -> None:
    # São Gabriel has had no telemetry since 2023
    assert "Sem dados recentes" in responder(n8n, "/nivel sao gabriel")


def test_unknown_command_shows_help(n8n: psycopg.Connection) -> None:
    assert "Comandos:" in responder(n8n, "oi")


def test_bulletin_covers_all_rivers(n8n: psycopg.Connection) -> None:
    linha = n8n.execute("SELECT bot.boletim()").fetchone()
    assert linha is not None
    for rio in ("Negro", "Solimões", "Madeira", "Amazonas"):
        assert f"Rio {rio}" in linha[0]
    assert linha[0].count("• ") == 10


def test_choose_alert_stations(n8n: psycopg.Connection) -> None:
    texto = responder(n8n, "/alertas manaus, humaitá")
    assert "Manaus, Humaitá" in texto
    ativo, estacoes, ultimos = inscrito(n8n)
    assert ativo and sorted(estacoes) == [MANAUS, "15630000"]
    # baseline recorded, so nothing is pending right after choosing
    assert set(ultimos) == {MANAUS, "15630000"}
    assert pendentes(n8n) == []
    assert "Manaus" in responder(n8n, "/alertas")


def test_unknown_alert_station_changes_nothing(n8n: psycopg.Connection) -> None:
    responder(n8n, "/alertas manaus")
    assert "Não encontrei: atlantida" in responder(n8n, "/alertas manaus, atlantida")
    assert inscrito(n8n)[1] == [MANAUS]


def test_all_and_none(n8n: psycopg.Connection) -> None:
    responder(n8n, "/alertas todas")
    assert len(inscrito(n8n)[1]) == 10
    responder(n8n, "/alertas nenhuma")
    assert inscrito(n8n)[1:] == ([], {})


def test_alert_fires_once_when_situation_changes(n8n: psycopg.Connection) -> None:
    responder(n8n, "/alertas manaus")
    n8n.execute(
        'UPDATE dados.inscritos SET ultimos_alertas = \'{"14990000": "alerta"}\' '
        "WHERE chat_id = %s",
        (CHAT,),
    )
    [(estacao, situacao, mensagem)] = pendentes(n8n)
    assert estacao == MANAUS and situacao != "alerta"
    assert "Antes: 🟠 Alerta" in mensagem
    n8n.execute("SELECT bot.marcar_alerta(%s, %s, %s)", (CHAT, estacao, situacao))
    assert pendentes(n8n) == []


def test_no_alerts_after_stop(n8n: psycopg.Connection) -> None:
    responder(n8n, "/alertas manaus")
    n8n.execute(
        "UPDATE dados.inscritos SET ultimos_alertas = '{}', ativo = false WHERE chat_id = %s",
        (CHAT,),
    )
    assert pendentes(n8n) == []
    assert CHAT not in [r[0] for r in n8n.execute("SELECT bot.inscritos_ativos()").fetchall()]


@pytest.mark.parametrize("user", ["rios_leitura", "rios_coletor"])
def test_only_n8n_runs_the_bot(connect: Connect, user: str) -> None:
    conn = connect(user)
    with pytest.raises(psycopg.errors.InsufficientPrivilege):
        conn.execute("SELECT bot.boletim()")


@pytest.mark.parametrize(
    ("erro", "desativa"),
    [
        ("Forbidden: bot was blocked by the user", True),
        ("403 - Forbidden: user is deactivated", True),
        ("400 - Bad Request: chat not found", True),
        ("429 - Too Many Requests: retry after 5", False),
        ("ETIMEDOUT", False),
    ],
)
def test_blocked_chat_is_deactivated(n8n: psycopg.Connection, erro: str, desativa: bool) -> None:
    responder(n8n, "/start")
    n8n.execute("SELECT bot.desativar_se_bloqueado(%s, %s)", (CHAT, erro))
    assert inscrito(n8n)[0] is (not desativa)
