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
    # Rios Amazônicos — coleta e limpeza

    Baixa as fontes, extrai as leituras e aplica a limpeza (Fase 3). Nada é
    gravado no banco ainda (Fase 4).

    | Fonte | O que vem | Unidade |
    |---|---|---|
    | **ANA, telemetria** | Leituras de 15 min a 1 h por estação | cm, horário de Brasília |
    | **Porto de Manaus** | Uma leitura por dia, digitada à mão | m, sem horário |

    **Amostras salvas** usa os arquivos de teste e não acessa a internet. **Ao vivo**
    consulta as fontes (no máximo 1 vez por hora). Rodando como script, a coleta é
    sempre ao vivo.
    """)
    return


@app.cell
def _(mo):
    origem = mo.ui.radio(
        options=["Amostras salvas", "Ao vivo"], value="Amostras salvas", label="Origem dos dados"
    )
    botao = mo.ui.run_button(label="Coletar ao vivo")
    mo.hstack([origem, botao], justify="start", gap=2)
    return botao, origem


@app.cell
def _(mo, origem):
    como_script = mo.app_meta().mode == "script"
    ao_vivo = como_script or origem.value == "Ao vivo"
    return (ao_vivo,)


@app.cell
def _(mo):
    from collections import Counter
    from datetime import date, timedelta

    import httpx

    from rios.banco import conectar_coletor, estacoes_ativas, faixas_historicas
    from rios.fontes import ana, porto
    from rios.fontes.http import TIMEOUT_SECONDS, USER_AGENT, baixar
    from rios.limpeza import FUSO_MANAUS, limpar_ana, limpar_porto

    with conectar_coletor() as conn:
        estacoes = estacoes_ativas(conn)
        faixas = faixas_historicas(conn)

    nomes = {estacao.codigo_ana: estacao.nome for estacao in estacoes}
    amostras = mo.notebook_dir().parent / "tests" / "fixtures"
    return (
        Counter,
        FUSO_MANAUS,
        TIMEOUT_SECONDS,
        USER_AGENT,
        amostras,
        ana,
        baixar,
        date,
        estacoes,
        faixas,
        httpx,
        limpar_ana,
        limpar_porto,
        nomes,
        porto,
        timedelta,
    )


@app.cell
def _(
    TIMEOUT_SECONDS,
    USER_AGENT,
    amostras,
    ana,
    ao_vivo,
    baixar,
    botao,
    date,
    estacoes,
    httpx,
    mo,
    porto,
    timedelta,
):
    mo.stop(
        ao_vivo and not botao.value and mo.app_meta().mode != "script",
        mo.md("_Clique em **Coletar ao vivo**._"),
    )

    def coletar_ao_vivo() -> tuple[list, list, list, str | None]:
        brutas_ana, resumo = [], []
        hoje = date.today()
        with httpx.Client(headers={"User-Agent": USER_AGENT}, timeout=TIMEOUT_SECONDS) as cliente:
            for estacao in estacoes:
                url = ana.url_dados(estacao.codigo_ana, hoje - timedelta(days=1), hoje)
                try:
                    resposta = baixar(url, cliente)
                    if not resposta.ok:
                        raise ana.RespostaAnaInvalida(f"HTTP {resposta.status_http}")
                    extraidas = ana.extrair(resposta.conteudo)
                    status = "ok"
                except (httpx.HTTPError, ana.RespostaAnaInvalida) as erro:
                    extraidas, status = [], f"falha: {erro}"
                brutas_ana.extend(extraidas)
                resumo.append({"estação": estacao.nome, "rio": estacao.rio, "status": status})
            try:
                resposta_porto = baixar(porto.URL, cliente)
                linhas = porto.extrair(resposta_porto.conteudo)
                erro_porto = None
            except (httpx.HTTPError, porto.PaginaPortoInvalida) as erro:
                linhas, erro_porto = [], str(erro)
        return brutas_ana, resumo, linhas, erro_porto

    def carregar_amostras() -> tuple[list, list, list, str | None]:
        brutas_ana = ana.extrair((amostras / "ana_14990000_2026-10-20.xml").read_bytes())
        linhas = porto.extrair((amostras / "porto_manaus_2026-10-20.html").read_bytes())
        resumo = [{"estação": "Manaus", "rio": "Negro", "status": "amostra salva"}]
        return brutas_ana, resumo, linhas, None

    brutas_ana, resumo_coleta, linhas_porto, erro_porto = (
        coletar_ao_vivo() if ao_vivo else carregar_amostras()
    )
    return brutas_ana, erro_porto, linhas_porto, resumo_coleta


@app.cell
def _(brutas_ana, faixas, limpar_ana, limpar_porto, linhas_porto):
    leituras_ana = limpar_ana(brutas_ana, faixa_historica=faixas)
    leituras_porto, lacunas_porto = limpar_porto(linhas_porto) if linhas_porto else ([], [])
    leituras = leituras_ana + leituras_porto
    return lacunas_porto, leituras, leituras_ana, leituras_porto


@app.cell
def _(Counter, leituras, mo):
    qualidade = Counter(leitura.qualidade for leitura in leituras)
    mo.hstack(
        [
            mo.stat(len(leituras), label="Leituras limpas"),
            mo.stat(qualidade["ok"], label="OK"),
            mo.stat(qualidade["corrigida"], label="Corrigidas"),
            mo.stat(qualidade["suspeita"], label="Suspeitas"),
        ],
        justify="start",
        gap=2,
    )
    return


@app.cell
def _(FUSO_MANAUS, leituras_ana, nomes):
    def ultima_por_estacao(leituras: list) -> list[dict]:
        ultimas = {}
        for leitura in leituras:
            if leitura.qualidade != "suspeita":
                ultimas[leitura.estacao] = leitura
        return [
            {
                "estação": nomes.get(codigo, codigo),
                "cota (m)": float(leitura.cota_cm) / 100,
                "horário (Manaus)": leitura.instante.astimezone(FUSO_MANAUS).strftime(
                    "%d/%m %H:%M"
                ),
            }
            for codigo, leitura in ultimas.items()
        ]

    situacao_atual = ultima_por_estacao(leituras_ana)
    return (situacao_atual,)


@app.cell
def _(FUSO_MANAUS, leituras, nomes):
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
    return (problemas,)


@app.cell
def _(
    erro_porto,
    lacunas_porto,
    leituras_porto,
    mo,
    problemas,
    resumo_coleta,
    situacao_atual,
):
    porto_texto = (
        mo.md(f"**Falha no Porto:** {erro_porto}")
        if erro_porto
        else mo.md(
            f"{len(leituras_porto)} dias limpos; "
            f"dias faltando: {', '.join(str(lacuna.dia) for lacuna in lacunas_porto) or 'nenhum'}."
        )
    )
    mo.ui.tabs(
        {
            "Situação atual (ANA)": mo.ui.table(situacao_atual, selection=None),
            "Correções e suspeitas": mo.vstack(
                [
                    mo.md("Valores **nunca são apagados**: o publicado fica guardado ao lado."),
                    mo.ui.table(problemas, selection=None),
                ]
            ),
            "Porto de Manaus": porto_texto,
            "Coleta": mo.ui.table(resumo_coleta, selection=None),
        }
    )
    return


@app.cell
def _(FUSO_MANAUS, leituras_ana, leituras_porto, mo):
    # Cross-check: Porto vs ANA for Manaus on the same local day
    ana_manaus = {
        leitura.instante.astimezone(FUSO_MANAUS).date(): leitura.cota_cm
        for leitura in leituras_ana
        if leitura.estacao == "14990000" and leitura.qualidade != "suspeita"
    }
    conferencia = [
        {
            "dia": str(dia),
            "Porto (m)": float(leitura.cota_cm) / 100,
            "ANA (m)": float(ana_manaus[dia]) / 100,
            "diferença (cm)": float(leitura.cota_cm - ana_manaus[dia]),
        }
        for leitura in leituras_porto
        if (dia := leitura.instante.date()) in ana_manaus and leitura.cota_cm is not None
    ]
    mo.vstack(
        [
            mo.md("## Conferência Manaus: Porto × ANA"),
            mo.ui.table(conferencia, selection=None)
            if conferencia
            else mo.md("_Sem dias em comum entre as duas fontes nesta coleta._"),
        ]
    )
    return


@app.cell
def _(Counter, leituras, mo, resumo_coleta):
    # Plain-text summary for script runs (cron/systemd logs)
    if mo.app_meta().mode == "script":
        for item in resumo_coleta:
            print(f"{item['estação']}: {item['status']}")
        print(f"Qualidade: {dict(Counter(leitura.qualidade for leitura in leituras))}")
    return


if __name__ == "__main__":
    app.run()
