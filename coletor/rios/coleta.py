"""Phase 4: one collection run per source = download -> raw layer -> clean -> upsert.

Each source gets its own row in ``dados.coletas``. A station or period that fails
does not stop the others; the run ends as ``sucesso``, ``parcial`` or ``falha``.
"""

import time
from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import date, timedelta
from decimal import Decimal

import httpx
import psycopg

from rios import banco
from rios.banco import Estacao
from rios.fontes import ana, porto
from rios.fontes.http import Resposta, baixar
from rios.limpeza import Lacuna, LeituraLimpa, limpar_ana, limpar_porto

# Longest period per ANA request (15-min readings: ~3k rows per month)
DIAS_POR_CONSULTA_ANA = 31


@dataclass
class ResultadoColeta:
    fonte: str
    coleta_id: int | None = None
    leituras: list[LeituraLimpa] = field(default_factory=list)
    leituras_novas: int = 0
    falhas: list[str] = field(default_factory=list)
    lacunas: list[Lacuna] = field(default_factory=list)
    consultas: int = 0

    @property
    def status(self) -> str:
        if not self.falhas:
            return "sucesso"
        return "parcial" if self.consultas > len(self.falhas) else "falha"


def periodos(inicio: date, fim: date, dias: int = DIAS_POR_CONSULTA_ANA) -> list[tuple[date, date]]:
    """Split [inicio, fim] into consecutive inclusive periods of at most ``dias`` days."""
    resultado = []
    atual = inicio
    while atual <= fim:
        ultimo = min(atual + timedelta(days=dias - 1), fim)
        resultado.append((atual, ultimo))
        atual = ultimo + timedelta(days=1)
    return resultado


def _executar(
    conn: psycopg.Connection | None,
    resultado: ResultadoColeta,
    corpo: Callable[[], None],
) -> ResultadoColeta:
    """Open/close the ``coletas`` row around ``corpo``; without ``conn`` nothing is written."""
    if conn is not None:
        resultado.coleta_id = banco.iniciar_coleta(conn, resultado.fonte)
    try:
        corpo()
    except Exception as erro:
        if conn is not None and resultado.coleta_id is not None:
            conn.rollback()
            banco.finalizar_coleta(
                conn, resultado.coleta_id, "falha", resultado.leituras_novas, repr(erro)
            )
        raise
    if conn is not None and resultado.coleta_id is not None:
        erro = "; ".join(resultado.falhas) or None
        banco.finalizar_coleta(
            conn, resultado.coleta_id, resultado.status, resultado.leituras_novas, erro
        )
    return resultado


def coletar_ana(
    cliente: httpx.Client,
    estacoes: list[Estacao],
    inicio: date,
    fim: date,
    conn: psycopg.Connection | None = None,
    faixas: dict[str, tuple[Decimal, Decimal]] | None = None,
    pausa_segundos: float = 0.0,
) -> ResultadoColeta:
    """Collect ANA telemetry for each station; commits station by station."""
    resultado = ResultadoColeta("ana_telemetria")

    def corpo() -> None:
        for estacao in estacoes:
            brutas: list[ana.LeituraAna] = []
            for de, ate in periodos(inicio, fim):
                if resultado.consultas and pausa_segundos:
                    time.sleep(pausa_segundos)
                resultado.consultas += 1
                url = ana.url_dados(estacao.codigo_ana, de, ate)
                try:
                    resposta = baixar(url, cliente)
                    _guardar_bruto(conn, resultado, resposta)
                    if not resposta.ok:
                        raise ana.RespostaAnaInvalida(f"HTTP {resposta.status_http}")
                    brutas.extend(ana.extrair(resposta.conteudo))
                except (httpx.HTTPError, ana.RespostaAnaInvalida) as erro:
                    resultado.falhas.append(f"{estacao.nome} {de:%d/%m/%Y}–{ate:%d/%m/%Y}: {erro}")
            limpas = limpar_ana(brutas, faixas)
            resultado.leituras.extend(limpas)
            if conn is not None and resultado.coleta_id is not None:
                resultado.leituras_novas += banco.gravar_leituras(conn, resultado.coleta_id, limpas)
                conn.commit()

    return _executar(conn, resultado, corpo)


def coletar_porto(cliente: httpx.Client, conn: psycopg.Connection | None = None) -> ResultadoColeta:
    resultado = ResultadoColeta("porto_manaus")

    def corpo() -> None:
        resultado.consultas = 1
        try:
            resposta = baixar(porto.URL, cliente)
            _guardar_bruto(conn, resultado, resposta)
            linhas = porto.extrair(resposta.conteudo)
        except (httpx.HTTPError, porto.PaginaPortoInvalida) as erro:
            resultado.falhas.append(str(erro))
            return
        resultado.leituras, resultado.lacunas = limpar_porto(linhas)
        if conn is not None and resultado.coleta_id is not None:
            resultado.leituras_novas = banco.gravar_leituras(
                conn, resultado.coleta_id, resultado.leituras
            )
            conn.commit()

    return _executar(conn, resultado, corpo)


def _guardar_bruto(
    conn: psycopg.Connection | None, resultado: ResultadoColeta, resposta: Resposta
) -> None:
    if conn is not None and resultado.coleta_id is not None:
        banco.salvar_resposta(conn, resultado.coleta_id, resultado.fonte, resposta)
