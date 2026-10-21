"""ANA telemetry (ServiceANA.asmx, DadosHidrometeorologicos).

Returns the values exactly as published (strings); level is in centimeters.
"""

from dataclasses import dataclass
from datetime import date
from urllib.parse import urlencode
from xml.etree import ElementTree

BASE_URL = "https://telemetriaws1.ana.gov.br/ServiceANA.asmx/DadosHidrometeorologicos"


@dataclass(frozen=True)
class LeituraAna:
    codigo_estacao: str
    data_hora: str
    nivel: str | None


class RespostaAnaInvalida(ValueError):
    """Response is not the expected XML (e.g. a 504 HTML page)."""


def url_dados(codigo_estacao: str, inicio: date, fim: date) -> str:
    query = urlencode(
        {
            "codEstacao": codigo_estacao,
            "dataInicio": inicio.strftime("%d/%m/%Y"),
            "dataFim": fim.strftime("%d/%m/%Y"),
        }
    )
    return f"{BASE_URL}?{query}"


def _texto(elemento: ElementTree.Element, tag: str) -> str | None:
    filho = elemento.find(tag)
    if filho is None or filho.text is None:
        return None
    texto = filho.text.strip()
    return texto or None


def extrair(conteudo: bytes) -> list[LeituraAna]:
    try:
        raiz = ElementTree.fromstring(conteudo)
    except ElementTree.ParseError as erro:
        raise RespostaAnaInvalida("not XML") from erro
    if not raiz.tag.endswith("DataTable"):
        raise RespostaAnaInvalida(f"unexpected root element: {raiz.tag}")

    leituras: list[LeituraAna] = []
    for registro in raiz.iter("DadosHidrometereologicos"):
        codigo = _texto(registro, "CodEstacao")
        data_hora = _texto(registro, "DataHora")
        if codigo is None or data_hora is None:
            continue
        leituras.append(LeituraAna(codigo, data_hora, _texto(registro, "Nivel")))
    return leituras
