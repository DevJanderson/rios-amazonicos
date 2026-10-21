"""Phase 2: extraction from ANA and Porto de Manaus (raw values, no cleaning)."""

from datetime import date
from pathlib import Path

import pytest

from rios.fontes import ana, porto

FIXTURES = Path(__file__).parent / "fixtures"
PORTO_HTML = (FIXTURES / "porto_manaus_2026-10-20.html").read_bytes()


# ---------------------------------------------------------------- ANA


def test_ana_url() -> None:
    url = ana.url_dados("14990000", date(2026, 10, 19), date(2026, 10, 20))
    assert url.endswith("codEstacao=14990000&dataInicio=19%2F10%2F2026&dataFim=20%2F10%2F2026")


def test_ana_real_capture() -> None:
    leituras = ana.extrair((FIXTURES / "ana_14990000_2026-10-20.xml").read_bytes())
    assert len(leituras) == 88
    assert leituras[0] == ana.LeituraAna("14990000", "2026-10-20 21:45:00", "1701.00")
    assert all(leitura.codigo_estacao == "14990000" for leitura in leituras)


def test_ana_extracts_readings_keeping_raw_values() -> None:
    leituras = ana.extrair((FIXTURES / "ana_sintetico.xml").read_bytes())
    assert len(leituras) == 3
    assert leituras[0] == ana.LeituraAna("14990000", "2026-10-20 20:45:00", "1703.00")
    assert leituras[1].nivel is None  # sensor without level


def test_ana_gateway_error_is_rejected() -> None:
    with pytest.raises(ana.RespostaAnaInvalida):
        ana.extrair((FIXTURES / "ana_erro_504.html").read_bytes())


# ---------------------------------------------------------------- Porto


def test_porto_extracts_six_months() -> None:
    linhas = porto.extrair(PORTO_HTML)
    meses = {(linha.ano, linha.mes) for linha in linhas}
    assert meses == {(2026, m) for m in range(5, 11)}


def test_porto_first_row_of_october() -> None:
    linhas = porto.extrair(PORTO_HTML)
    outubro = [linha for linha in linhas if linha.mes == 10]
    assert outubro[0] == porto.LinhaPorto(10, 2026, "1", "18.73", "-15.00")


def test_porto_keeps_known_source_problems_for_cleaning() -> None:
    junho = [linha for linha in porto.extrair(PORTO_HTML) if linha.mes == 6]
    dias = [linha.dia for linha in junho]
    assert dias.count("19") == 2  # duplicated day
    assert "18" not in dias  # missing day
    dia_6 = next(linha for linha in junho if linha.dia == "6")
    assert dia_6.cota_m == "20.12"  # typo, correct value is 28.12
    assert any("," in linha.variacao_cm for linha in junho)  # decimal comma


def test_porto_invalid_page() -> None:
    with pytest.raises(porto.PaginaPortoInvalida):
        porto.extrair("<html><body>sem tabela</body></html>")
