"""Phase 3: turn raw extracted values into clean readings with explicit quality.

Rules (docs/dados.md):
- level always in centimeters (Decimal), timestamps timezone-aware;
- the original text is kept in ``cota_original``;
- nothing is silently dropped or overwritten: problems become ``suspeita`` or
  ``corrigida`` with a ``motivo``.
"""

from dataclasses import dataclass, replace
from datetime import date, datetime, time
from decimal import Decimal, InvalidOperation
from zoneinfo import ZoneInfo

from rios.fontes.ana import LeituraAna
from rios.fontes.porto import LinhaPorto

# ANA telemetry timestamps are in Brasília time (UTC-3): a Manaus reading stamped
# 21:45 was already available at 22:07 UTC-3 on 2026-10-20.
FUSO_ANA = ZoneInfo("America/Sao_Paulo")
FUSO_MANAUS = ZoneInfo("America/Manaus")

PORTO_MANAUS = "14990000"

# Porto publishes one reading per day without the hour; use a fixed local time.
HORA_LEITURA_PORTO = time(0, 0)

# Largest plausible change between consecutive readings. Big rivers move a few
# cm per hour; Manaus' fastest daily change on record is well under 50 cm.
SALTO_MAXIMO_POR_HORA_CM = Decimal(30)
SALTO_MAXIMO_DIARIO_CM = Decimal(60)
# Tolerance when checking "previous level + published change == level".
TOLERANCIA_VARIACAO_CM = Decimal(2)


@dataclass(frozen=True)
class LeituraLimpa:
    estacao: str
    instante: datetime
    fonte: str
    cota_cm: Decimal | None
    cota_original: str
    qualidade: str = "ok"
    motivo: str | None = None


@dataclass(frozen=True)
class Lacuna:
    estacao: str
    dia: date


def decimal_br(texto: str | None) -> Decimal | None:
    """Parse "5.00", "5,00", "-8.00", " 17.21 " into Decimal; None when empty/invalid."""
    if texto is None:
        return None
    texto = texto.strip().replace(",", ".")
    if not texto:
        return None
    try:
        return Decimal(texto)
    except InvalidOperation:
        return None


def _suspeita(leitura: LeituraLimpa, motivo: str) -> LeituraLimpa:
    return replace(leitura, qualidade="suspeita", motivo=motivo)


# ---------------------------------------------------------------- ANA


def limpar_ana(
    brutas: list[LeituraAna],
    faixa_historica: dict[str, tuple[Decimal, Decimal]] | None = None,
) -> list[LeituraLimpa]:
    """Clean ANA readings. Readings without level are dropped (nothing to store).

    ``faixa_historica`` maps station -> (min, max) in cm; values far outside the
    historical range are marked suspicious.
    """
    limpas: list[LeituraLimpa] = []
    for bruta in brutas:
        cota = decimal_br(bruta.nivel)
        if cota is None:
            continue
        instante = datetime.fromisoformat(bruta.data_hora.strip()).replace(tzinfo=FUSO_ANA)
        limpas.append(
            LeituraLimpa(bruta.codigo_estacao, instante, "ana_telemetria", cota, bruta.nivel or "")
        )

    # Same station + instant may come twice in overlapping queries: keep one.
    unicas = {(leitura.estacao, leitura.instante): leitura for leitura in limpas}
    ordenadas = sorted(unicas.values(), key=lambda leitura: (leitura.estacao, leitura.instante))
    return _marcar_saltos(_marcar_fora_da_faixa(ordenadas, faixa_historica or {}))


def _marcar_fora_da_faixa(
    leituras: list[LeituraLimpa], faixa: dict[str, tuple[Decimal, Decimal]]
) -> list[LeituraLimpa]:
    margem = Decimal(300)  # 3 m beyond the record: certainly not a real level
    resultado = []
    for leitura in leituras:
        limites = faixa.get(leitura.estacao)
        if limites and leitura.cota_cm is not None:
            minima, maxima = limites
            if not (minima - margem <= leitura.cota_cm <= maxima + margem):
                leitura = _suspeita(leitura, "fora da faixa histórica")
        resultado.append(leitura)
    return resultado


def _marcar_saltos(leituras: list[LeituraLimpa]) -> list[LeituraLimpa]:
    """Mark a reading suspicious when it jumps away from both neighbors."""
    resultado = list(leituras)
    for i in range(1, len(leituras) - 1):
        anterior, atual, seguinte = leituras[i - 1], leituras[i], leituras[i + 1]
        if not (anterior.estacao == atual.estacao == seguinte.estacao):
            continue
        if atual.qualidade != "ok" or None in (anterior.cota_cm, atual.cota_cm, seguinte.cota_cm):
            continue
        assert anterior.cota_cm is not None and atual.cota_cm is not None
        assert seguinte.cota_cm is not None
        horas = max((seguinte.instante - anterior.instante).total_seconds() / 3600, 1)
        limite = SALTO_MAXIMO_POR_HORA_CM * Decimal(str(horas))
        if (
            abs(atual.cota_cm - anterior.cota_cm) > limite
            and abs(atual.cota_cm - seguinte.cota_cm) > limite
            and abs(seguinte.cota_cm - anterior.cota_cm) <= limite
        ):
            resultado[i] = _suspeita(atual, "salto brusco em relação às leituras vizinhas")
    return resultado


# ---------------------------------------------------------------- Porto de Manaus


@dataclass(frozen=True)
class _LinhaPorto:
    dia: date
    cota_cm: Decimal | None
    variacao_cm: Decimal | None
    original: str
    motivo_dia: str | None


def _corrigir_dias(linhas: list[LinhaPorto]) -> list[_LinhaPorto]:
    """Fix a duplicated day that stands in for a missing one (Jun/2026: 17, 19, 19, 20).

    A row whose day skips ahead while the next row repeats that same day is the
    missing day typed wrong.
    """
    resultado: list[_LinhaPorto] = []
    dia_anterior = 0
    for i, linha in enumerate(linhas):
        dia = int(linha.dia)
        esperado = dia_anterior + 1
        proximo = int(linhas[i + 1].dia) if i + 1 < len(linhas) else None
        motivo = None
        if dia != esperado and proximo == dia and dia_anterior > 0:
            motivo = f"dia publicado como {dia}, corrigido para {esperado} (dia repetido)"
            dia = esperado
        cota_m = decimal_br(linha.cota_m)
        resultado.append(
            _LinhaPorto(
                date(linha.ano, linha.mes, dia),
                cota_m * 100 if cota_m is not None else None,
                decimal_br(linha.variacao_cm),
                linha.cota_m,
                motivo,
            )
        )
        dia_anterior = dia
    return resultado


def _corrigir_digitacao(linhas: list[_LinhaPorto]) -> list[LeituraLimpa]:
    """Detect a level that disagrees with both neighbors and fix it when the
    published daily change confirms the value (prev + change == fixed == next - next change).
    """
    leituras: list[LeituraLimpa] = []
    for i, linha in enumerate(linhas):
        instante = datetime.combine(linha.dia, HORA_LEITURA_PORTO, FUSO_MANAUS)
        leitura = LeituraLimpa(
            PORTO_MANAUS, instante, "porto_manaus", linha.cota_cm, linha.original
        )
        if linha.motivo_dia:
            leitura = replace(leitura, qualidade="corrigida", motivo=linha.motivo_dia)

        anterior = linhas[i - 1] if i > 0 else None
        seguinte = linhas[i + 1] if i + 1 < len(linhas) else None
        if (
            anterior
            and seguinte
            and None
            not in (
                anterior.cota_cm,
                linha.cota_cm,
                seguinte.cota_cm,
            )
        ):
            assert anterior.cota_cm is not None and linha.cota_cm is not None
            assert seguinte.cota_cm is not None
            fora = (
                abs(linha.cota_cm - anterior.cota_cm) > SALTO_MAXIMO_DIARIO_CM
                and abs(linha.cota_cm - seguinte.cota_cm) > SALTO_MAXIMO_DIARIO_CM
            )
            if fora:
                leitura = _corrigir_pela_variacao(leitura, anterior, linha, seguinte)
        leituras.append(leitura)
    return leituras


def _corrigir_pela_variacao(
    leitura: LeituraLimpa, anterior: _LinhaPorto, linha: _LinhaPorto, seguinte: _LinhaPorto
) -> LeituraLimpa:
    assert anterior.cota_cm is not None and seguinte.cota_cm is not None
    if linha.variacao_cm is None or seguinte.variacao_cm is None:
        return _suspeita(leitura, "salto brusco em relação aos dias vizinhos")
    pela_anterior = anterior.cota_cm + linha.variacao_cm
    pela_seguinte = seguinte.cota_cm - seguinte.variacao_cm
    if abs(pela_anterior - pela_seguinte) > TOLERANCIA_VARIACAO_CM:
        return _suspeita(leitura, "salto brusco em relação aos dias vizinhos")
    publicado = leitura.cota_cm / 100 if leitura.cota_cm is not None else None
    return replace(
        leitura,
        cota_cm=pela_anterior,
        qualidade="corrigida",
        motivo=(
            f"erro de digitação: publicado {publicado} m, corrigido para "
            f"{pela_anterior / 100} m (cota anterior + variação, confere com o dia seguinte)"
        ),
    )


def limpar_porto(linhas: list[LinhaPorto]) -> tuple[list[LeituraLimpa], list[Lacuna]]:
    """Clean the Porto de Manaus tables. Returns readings and days still missing."""
    por_mes: dict[tuple[int, int], list[LinhaPorto]] = {}
    for linha in linhas:
        por_mes.setdefault((linha.ano, linha.mes), []).append(linha)

    leituras: list[LeituraLimpa] = []
    for chave in sorted(por_mes):
        validas = [linha for linha in por_mes[chave] if linha.dia.strip().isdigit()]
        leituras.extend(_corrigir_digitacao(_corrigir_dias(validas)))

    # A day still duplicated after correction: keep the first, flag it, drop the copy.
    por_dia: dict[date, LeituraLimpa] = {}
    for leitura in leituras:
        dia = leitura.instante.date()
        if dia in por_dia:
            primeira = por_dia[dia]
            por_dia[dia] = _suspeita(
                primeira, f"dia duplicado; outro valor publicado: {leitura.cota_original} m"
            )
        else:
            por_dia[dia] = leitura

    dias = sorted(por_dia)
    return [por_dia[dia] for dia in dias], _lacunas(dias)


def _lacunas(dias: list[date]) -> list[Lacuna]:
    lacunas = []
    for anterior, seguinte in zip(dias, dias[1:], strict=False):
        faltando = (seguinte - anterior).days - 1
        lacunas.extend(
            Lacuna(PORTO_MANAUS, date.fromordinal(anterior.toordinal() + n))
            for n in range(1, faltando + 1)
        )
    return lacunas
