"""Porto de Manaus: monthly tables "Dia | Cota (m) | Encheu/Vazou (cm)".

Returns the cells exactly as published (strings); cleaning happens in Phase 3.
"""

import re
from dataclasses import dataclass

from selectolax.lexbor import LexborHTMLParser, LexborNode

URL = "https://portodemanaus.com.br/nivel-do-rio-negro/"

MESES = [
    "Janeiro",
    "Fevereiro",
    "Março",
    "Abril",
    "Maio",
    "Junho",
    "Julho",
    "Agosto",
    "Setembro",
    "Outubro",
    "Novembro",
    "Dezembro",
]
_TITULO_MES = re.compile(rf"({'|'.join(MESES)})\s*/?\s*(\d{{4}})")
_NIVEIS_ATE_TITULO = 8


@dataclass(frozen=True)
class LinhaPorto:
    mes: int
    ano: int
    dia: str
    cota_m: str
    variacao_cm: str


class PaginaPortoInvalida(ValueError):
    """Page layout changed: no monthly table found."""


def _mes_da_tabela(tabela: LexborNode) -> tuple[int, int] | None:
    """Find the "Outubro 2026" title in the nearest enclosing block."""
    no: LexborNode | None = tabela
    for _ in range(_NIVEIS_ATE_TITULO):
        no = no.parent if no is not None else None
        if no is None:
            return None
        achado = _TITULO_MES.search(no.text(separator=" ", strip=True))
        if achado:
            return MESES.index(achado.group(1)) + 1, int(achado.group(2))
    return None


def extrair(html: str | bytes) -> list[LinhaPorto]:
    if isinstance(html, bytes):
        html = html.decode("utf-8", errors="replace")
    pagina = LexborHTMLParser(html)

    linhas: list[LinhaPorto] = []
    for tabela in pagina.css("table"):
        mes_ano = _mes_da_tabela(tabela)
        if mes_ano is None:
            continue
        mes, ano = mes_ano
        for tr in tabela.css("tr"):
            celulas = [td.text(strip=True) for td in tr.css("td")]
            if len(celulas) != 3:
                continue  # header row (th) or broken row
            dia, cota, variacao = celulas
            linhas.append(LinhaPorto(mes, ano, dia, cota, variacao))

    if not linhas:
        raise PaginaPortoInvalida("no monthly table found")
    return linhas
