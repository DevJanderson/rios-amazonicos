"""Phase 3: cleaning rules, using the real fixtures and small hand-made cases."""

from collections import Counter
from datetime import date, datetime, timedelta
from decimal import Decimal
from pathlib import Path

import pytest

from rios.fontes import ana, porto
from rios.fontes.ana import LeituraAna
from rios.fontes.porto import LinhaPorto
from rios.limpeza import (
    FUSO_ANA,
    FUSO_MANAUS,
    Lacuna,
    decimal_br,
    limpar_ana,
    limpar_porto,
)

FIXTURES = Path(__file__).parent / "fixtures"


@pytest.fixture(scope="module")
def porto_real() -> list:
    linhas = porto.extrair((FIXTURES / "porto_manaus_2026-10-20.html").read_bytes())
    leituras, lacunas = limpar_porto(linhas)
    assert lacunas == []
    return leituras


def por_dia(leituras: list, dia: date):
    return next(leitura for leitura in leituras if leitura.instante.date() == dia)


# ---------------------------------------------------------------- numbers


@pytest.mark.parametrize(
    ("texto", "esperado"),
    [
        ("5.00", Decimal("5.00")),
        ("5,00", Decimal("5.00")),
        ("-8.00", Decimal("-8.00")),
        (" 17.21 ", Decimal("17.21")),
        ("", None),
        (None, None),
        ("abc", None),
    ],
)
def test_decimal_br(texto: str | None, esperado: Decimal | None) -> None:
    assert decimal_br(texto) == esperado


# ---------------------------------------------------------------- Porto (real page)


def test_porto_levels_in_cm_and_local_date(porto_real: list) -> None:
    primeira = por_dia(porto_real, date(2026, 10, 1))
    assert primeira.cota_cm == Decimal("1873")
    assert primeira.cota_original == "18.73"
    assert primeira.instante.tzinfo == FUSO_MANAUS
    assert primeira.qualidade == "ok"


def test_porto_typo_fixed_by_published_change(porto_real: list) -> None:
    leitura = por_dia(porto_real, date(2026, 6, 6))
    assert leitura.cota_original == "20.12"
    assert leitura.cota_cm == Decimal("2812")
    assert leitura.qualidade == "corrigida"
    assert leitura.motivo is not None and "digitação" in leitura.motivo


def test_porto_duplicated_day_becomes_missing_day(porto_real: list) -> None:
    dia_18 = por_dia(porto_real, date(2026, 6, 18))
    dia_19 = por_dia(porto_real, date(2026, 6, 19))
    assert dia_18.cota_cm == Decimal("2848")
    assert dia_18.qualidade == "corrigida"
    assert dia_19.cota_cm == Decimal("2849")
    assert dia_19.qualidade == "ok"


def test_porto_decimal_comma_in_change_column_is_accepted(porto_real: list) -> None:
    # June uses "4,00" in the change column; the level of 06/07 is untouched
    assert por_dia(porto_real, date(2026, 6, 7)).qualidade == "ok"


def test_porto_one_reading_per_day_and_only_known_fixes(porto_real: list) -> None:
    dias = [leitura.instante.date() for leitura in porto_real]
    assert len(dias) == len(set(dias)) == 173
    assert Counter(leitura.qualidade for leitura in porto_real) == {"ok": 171, "corrigida": 2}


# ---------------------------------------------------------------- Porto (hand-made)


def linhas_porto(*valores: tuple[str, str, str]) -> list[LinhaPorto]:
    return [LinhaPorto(6, 2026, dia, cota, var) for dia, cota, var in valores]


def test_porto_typo_without_consistent_change_is_only_suspicious() -> None:
    leituras, _ = limpar_porto(
        linhas_porto(("1", "28.00", "1.00"), ("2", "20.12", "9.00"), ("3", "28.02", "1.00"))
    )
    assert leituras[1].qualidade == "suspeita"
    assert leituras[1].cota_cm == Decimal("2012")  # value kept as published


def test_porto_missing_day_is_reported() -> None:
    _, lacunas = limpar_porto(
        linhas_porto(("1", "28.00", "1.00"), ("2", "28.01", "1.00"), ("4", "28.03", "1.00"))
    )
    assert lacunas == [Lacuna("14990000", date(2026, 6, 3))]


def test_porto_duplicate_that_cannot_be_fixed_is_suspicious() -> None:
    leituras, _ = limpar_porto(
        linhas_porto(("1", "28.00", "1.00"), ("2", "28.01", "1.00"), ("2", "28.05", "1.00"))
    )
    assert len(leituras) == 2
    assert leituras[1].qualidade == "suspeita"
    assert leituras[1].motivo is not None and "28.05" in leituras[1].motivo


# ---------------------------------------------------------------- ANA


def test_ana_real_capture_is_clean() -> None:
    leituras = limpar_ana(ana.extrair((FIXTURES / "ana_14990000_2026-10-20.xml").read_bytes()))
    assert len(leituras) == 88
    assert all(leitura.qualidade == "ok" for leitura in leituras)
    ultima = leituras[-1]
    assert ultima.cota_cm == Decimal("1701.00")
    assert ultima.instante == datetime(2026, 10, 20, 21, 45, tzinfo=FUSO_ANA)
    # 21:45 Brasília is 20:45 in Manaus
    assert ultima.instante.astimezone(FUSO_MANAUS).hour == 20


def test_ana_drops_empty_level_and_sorts() -> None:
    leituras = limpar_ana(ana.extrair((FIXTURES / "ana_sintetico.xml").read_bytes()))
    assert [leitura.cota_cm for leitura in leituras] == [Decimal("1704.00"), Decimal("1703.00")]


def serie_ana(*cotas: str, inicio: datetime = datetime(2026, 10, 20, 10)) -> list[LeituraAna]:
    return [
        LeituraAna("14990000", str(inicio + timedelta(minutes=15 * i)), cota)
        for i, cota in enumerate(cotas)
    ]


def test_ana_spike_between_neighbors_is_suspicious() -> None:
    leituras = limpar_ana(serie_ana("1700", "1701", "2500", "1701", "1702"))
    qualidades = [leitura.qualidade for leitura in leituras]
    assert qualidades == ["ok", "ok", "suspeita", "ok", "ok"]
    assert leituras[2].cota_cm == Decimal("2500")  # kept, only flagged


def test_ana_gradual_rise_is_not_a_spike() -> None:
    leituras = limpar_ana(serie_ana("1700", "1702", "1704", "1706"))
    assert all(leitura.qualidade == "ok" for leitura in leituras)


def test_ana_out_of_historical_range() -> None:
    faixa = {"14990000": (Decimal(1213), Decimal(3002))}
    leituras = limpar_ana(serie_ana("170", "171"), faixa_historica=faixa)
    assert all(leitura.motivo == "fora da faixa histórica" for leitura in leituras)


def test_ana_repeated_reading_in_overlapping_queries_is_kept_once() -> None:
    brutas = serie_ana("1700", "1701")
    assert len(limpar_ana(brutas + brutas)) == 2
