import marimo

__generated_with = "0.25.2"
app = marimo.App(width="medium", app_title="Rios Amazônicos — coleta")


@app.cell
def _():
    import marimo as mo

    return (mo,)


@app.cell
def _(mo):
    mo.md(r"""
    # Rios Amazônicos — coleta

    Baixa as fontes, guarda a resposta original (camada `bruto`), limpa e grava as
    leituras (camada `dados`). Rodar de novo não duplica nada.

    | Fonte | O que vem | Unidade |
    |---|---|---|
    | **ANA, telemetria** | Leituras de 15 min a 1 h (histórico ~2011) | cm, hora de Brasília |
    | **Porto de Manaus** | Uma leitura por dia, digitada à mão | m, sem horário |

    **Como script** (agendado de hora em hora), coleta os últimos dias e grava:

    ```bash
    uv run python notebooks/coleta.py                       # padrão: 2 dias, grava
    uv run python notebooks/coleta.py -- --inicio 2024-01-01 --fim 2024-12-31 \
        --fontes ana --pausa 5                               # carga histórica
    uv run python notebooks/coleta.py -- --help
    ```
    """)
    return


@app.cell
def _():
    from collections import Counter
    from dataclasses import dataclass, fields
    from datetime import date, timedelta

    import httpx

    from rios import banco, coleta
    from rios.fontes.http import TIMEOUT_SECONDS, USER_AGENT
    from rios.limpeza import FUSO_MANAUS

    @dataclass(frozen=True)
    class Parametros:
        """Run settings, from the form (editor) or from the CLI (script)."""

        inicio: date
        fim: date
        fontes: tuple[str, ...] = ("ana", "porto")
        estacoes: tuple[str, ...] = ()  # empty = all active stations
        pausa: float = 0.0  # seconds between ANA requests (use > 0 for backfills)
        gravar: bool = True

    AJUDA = {
        "inicio": "Primeiro dia (AAAA-MM-DD). Padrão: ontem.",
        "fim": "Último dia (AAAA-MM-DD). Padrão: hoje.",
        "fontes": "ana, porto ou ana,porto. Padrão: ana,porto.",
        "estacoes": "Códigos ANA separados por vírgula. Padrão: todas as ativas.",
        "pausa": "Segundos entre consultas à ANA. Padrão: 0.",
        "gravar": "true/false. Padrão: true.",
    }
    return (
        AJUDA,
        Counter,
        FUSO_MANAUS,
        Parametros,
        TIMEOUT_SECONDS,
        USER_AGENT,
        banco,
        coleta,
        date,
        fields,
        httpx,
        timedelta,
    )


@app.cell
def _(banco):
    with banco.conectar_coletor() as conexao_leitura:
        estacoes = banco.estacoes_ativas(conexao_leitura)
        faixas = banco.faixas_historicas(conexao_leitura)
    nomes = {estacao.codigo_ana: estacao.nome for estacao in estacoes}
    return estacoes, faixas, nomes


@app.cell
def _(date, estacoes, mo, timedelta):
    formulario = (
        mo.md("""
        **Período:** {inicio} até {fim}

        **Fontes:** {fontes} &nbsp; **Estações:** {estacoes}

        **Pausa entre consultas (s):** {pausa} &nbsp; {gravar}
        """)
        .batch(
            inicio=mo.ui.date(value=date.today() - timedelta(days=1)),
            fim=mo.ui.date(value=date.today()),
            fontes=mo.ui.multiselect(options=["ana", "porto"], value=["ana", "porto"]),
            estacoes=mo.ui.multiselect(
                options={f"{e.rio} · {e.nome}": e.codigo_ana for e in estacoes},
                label="",
            ),
            pausa=mo.ui.number(start=0, stop=60, step=1, value=0),
            gravar=mo.ui.checkbox(label="Gravar no banco", value=False),
        )
        .form(submit_button_label="Coletar ao vivo")
    )
    formulario
    return (formulario,)


@app.cell
def _(AJUDA, Parametros, date, fields, formulario, mo, timedelta):
    como_script = mo.app_meta().mode == "script"

    def parametros_da_cli(argumentos: dict) -> Parametros:
        def lista(valor: object) -> tuple[str, ...]:
            return tuple(item.strip() for item in str(valor).split(",") if item.strip())

        ontem = date.today() - timedelta(days=1)
        return Parametros(
            inicio=date.fromisoformat(str(argumentos.get("inicio", ontem))),
            fim=date.fromisoformat(str(argumentos.get("fim", date.today()))),
            fontes=lista(argumentos.get("fontes", "ana,porto")),
            estacoes=lista(argumentos.get("estacoes", "")),
            pausa=float(argumentos.get("pausa", 0)),
            gravar=str(argumentos.get("gravar", "true")).lower() != "false",
        )

    if como_script and "help" in mo.cli_args():
        print("Uso: uv run python notebooks/coleta.py -- [--opção valor ...]\n")
        for campo in fields(Parametros):
            print(f"  --{campo.name:10s} {AJUDA[campo.name]}")
        raise SystemExit(0)

    if como_script:
        parametros = parametros_da_cli(mo.cli_args())
    else:
        mo.stop(formulario.value is None, mo.md("_Ajuste e clique em **Coletar ao vivo**._"))
        parametros = Parametros(
            inicio=formulario.value["inicio"],
            fim=formulario.value["fim"],
            fontes=tuple(formulario.value["fontes"]),
            estacoes=tuple(formulario.value["estacoes"]),
            pausa=float(formulario.value["pausa"]),
            gravar=formulario.value["gravar"],
        )
    return (parametros,)


@app.cell
def _(
    TIMEOUT_SECONDS,
    USER_AGENT,
    banco,
    coleta,
    estacoes,
    faixas,
    httpx,
    parametros,
):
    selecionadas = [
        e for e in estacoes if not parametros.estacoes or e.codigo_ana in parametros.estacoes
    ]
    conexao = banco.conectar_coletor() if parametros.gravar else None
    with httpx.Client(headers={"User-Agent": USER_AGENT}, timeout=TIMEOUT_SECONDS) as cliente:
        resultados = []
        if "ana" in parametros.fontes:
            resultados.append(
                coleta.coletar_ana(
                    cliente,
                    selecionadas,
                    parametros.inicio,
                    parametros.fim,
                    conn=conexao,
                    faixas=faixas,
                    pausa_segundos=parametros.pausa,
                )
            )
        if "porto" in parametros.fontes:
            resultados.append(coleta.coletar_porto(cliente, conn=conexao))
    if conexao is not None:
        brutos_apagados = banco.apagar_brutos_antigos(conexao)
        conexao.close()
    else:
        brutos_apagados = 0
    leituras = [leitura for resultado in resultados for leitura in resultado.leituras]
    return brutos_apagados, leituras, resultados


@app.cell
def _(Counter, leituras, mo, parametros, resultados):
    qualidade = Counter(leitura.qualidade for leitura in leituras)
    mo.vstack(
        [
            mo.hstack(
                [
                    mo.stat(len(leituras), label="Leituras limpas"),
                    mo.stat(
                        sum(r.leituras_novas for r in resultados), label="Novas/alteradas no banco"
                    ),
                    mo.stat(qualidade["corrigida"], label="Corrigidas"),
                    mo.stat(qualidade["suspeita"], label="Suspeitas"),
                ],
                justify="start",
                gap=2,
            ),
            mo.md("" if parametros.gravar else "_Prévia: nada foi gravado no banco._"),
        ]
    )
    return


@app.cell
def _(FUSO_MANAUS, leituras, nomes):
    ultimas = {}
    for leitura in leituras:
        if leitura.qualidade != "suspeita" and leitura.fonte == "ana_telemetria":
            ultimas[leitura.estacao] = leitura
    situacao_atual = [
        {
            "estação": nomes.get(codigo, codigo),
            "cota (m)": float(leitura.cota_cm) / 100,
            "horário (Manaus)": leitura.instante.astimezone(FUSO_MANAUS).strftime("%d/%m %H:%M"),
        }
        for codigo, leitura in ultimas.items()
    ]
    problemas = [
        {
            "estação": nomes.get(leitura.estacao, leitura.estacao),
            "fonte": leitura.fonte,
            "data (Manaus)": leitura.instante.astimezone(FUSO_MANAUS).strftime("%d/%m/%Y %H:%M"),
            "publicado": leitura.cota_original,
            "cota final (m)": float(leitura.cota_cm) / 100 if leitura.cota_cm is not None else None,
            "qualidade": leitura.qualidade,
            "motivo": leitura.motivo,
        }
        for leitura in leituras
        if leitura.qualidade != "ok"
    ]
    return problemas, situacao_atual


@app.cell
def _(brutos_apagados, mo, problemas, resultados, situacao_atual):
    resumo_execucao = [
        {
            "fonte": r.fonte,
            "coleta": r.coleta_id,
            "status": r.status,
            "consultas": r.consultas,
            "novas/alteradas": r.leituras_novas,
            "dias faltando": ", ".join(str(lacuna.dia) for lacuna in r.lacunas) or "—",
            "falhas": "; ".join(r.falhas) or "—",
        }
        for r in resultados
    ]
    mo.ui.tabs(
        {
            "Situação atual (ANA)": mo.ui.table(situacao_atual, selection=None),
            "Correções e suspeitas": mo.vstack(
                [
                    mo.md("Valores **nunca são apagados**: o publicado fica guardado ao lado."),
                    mo.ui.table(problemas, selection=None),
                ]
            ),
            "Execução": mo.vstack(
                [
                    mo.ui.table(resumo_execucao, selection=None),
                    mo.md(f"Respostas brutas com mais de 90 dias apagadas: {brutos_apagados}."),
                ]
            ),
        }
    )
    return


@app.cell
def _(Counter, leituras, mo, resultados):
    # Plain-text summary for script runs (systemd journal)
    if mo.app_meta().mode == "script":
        for resultado in resultados:
            print(
                f"{resultado.fonte}: {resultado.status}, coleta {resultado.coleta_id}, "
                f"{resultado.leituras_novas} novas/alteradas, {len(resultado.falhas)} falhas"
            )
            for falha in resultado.falhas:
                print(f"  falha: {falha}")
        print(f"qualidade: {dict(Counter(leitura.qualidade for leitura in leituras))}")
    return


if __name__ == "__main__":
    app.run()
