import marimo

__generated_with = "0.25.2"
app = marimo.App(width="medium", app_title="Rios Amazônicos — painel")


@app.cell
def _():
    import marimo as mo

    return (mo,)


@app.cell
def _(mo):
    mo.md(r"""
    # Rios Amazônicos — painel

    Cotas dos rios **Negro, Solimões, Madeira e Amazonas** a partir da telemetria da ANA,
    com cotas de referência do SGB. Só leitura (usuário `rios_leitura`, camada `analise`);
    leituras marcadas como suspeitas ficam de fora.

    _O zero de cada régua é próprio da estação: compare a variação, não o valor
    absoluto, entre estações diferentes._
    """)
    return


@app.cell
def _():
    from datetime import date

    import altair as alt
    import pandas as pd

    from rios import banco

    SITUACOES = {
        "inundacao_severa": "🟣 Inundação severa",
        "inundacao": "🔴 Inundação",
        "alerta": "🟠 Alerta",
        "atencao": "🟡 Atenção",
        "emergencia_seca": "🟤 Emergência de seca",
        "normal": "🟢 Normal",
        "sem_referencia": "⚪ Sem referência",
    }
    REFERENCIAS = {
        "atencao": "Atenção",
        "alerta": "Alerta",
        "inundacao": "Inundação",
        "inundacao_severa": "Inundação severa",
        "emergencia_seca": "Emergência de seca",
        "maxima_historica": "Máxima histórica",
        "minima_historica": "Mínima histórica",
    }
    # Vega-Lite locale: Portuguese month names and decimal comma in the charts
    LOCALE_PT = {
        "number": {"decimal": ",", "thousands": ".", "grouping": [3], "currency": ["R$ ", ""]},
        "time": {
            "dateTime": "%A, %e de %B de %Y. %X",
            "date": "%d/%m/%Y",
            "time": "%H:%M:%S",
            "periods": ["AM", "PM"],
            "days": ["Domingo", "Segunda", "Terça", "Quarta", "Quinta", "Sexta", "Sábado"],
            "shortDays": ["Dom", "Seg", "Ter", "Qua", "Qui", "Sex", "Sáb"],
            "months": [
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
            ],
            "shortMonths": [
                "Jan",
                "Fev",
                "Mar",
                "Abr",
                "Mai",
                "Jun",
                "Jul",
                "Ago",
                "Set",
                "Out",
                "Nov",
                "Dez",
            ],
        },
    }
    return LOCALE_PT, REFERENCIAS, SITUACOES, alt, banco, date, pd


@app.cell
def _(banco, pd):
    def consultar(sql: str) -> pd.DataFrame:
        with banco.conectar_leitura() as conexao:
            cursor = conexao.execute(sql)
            colunas = [coluna.name for coluna in cursor.description or []]
            return pd.DataFrame(cursor.fetchall(), columns=colunas)

    estacoes = consultar(
        "SELECT codigo_ana, nome, rio, rio_id, ordem_no_rio FROM analise.estacoes "
        "WHERE ativa ORDER BY rio_id, ordem_no_rio"
    )
    situacao = consultar("SELECT * FROM analise.situacao_estacao")
    referencias = consultar("SELECT estacao, tipo, cota_cm, fonte FROM analise.cotas_vigentes")
    diarias = consultar("SELECT estacao, dia, cota_cm FROM analise.leituras_diarias")
    coletas = consultar("SELECT * FROM analise.coletas_recentes ORDER BY inicio DESC")
    qualidade = consultar("SELECT * FROM analise.qualidade_mensal")

    diarias = diarias.assign(
        dia=pd.to_datetime(diarias["dia"]),
        cota_m=diarias["cota_cm"].astype(float) / 100,
    ).merge(estacoes, left_on="estacao", right_on="codigo_ana")
    return coletas, diarias, estacoes, qualidade, referencias, situacao


@app.cell
def _(SITUACOES, estacoes, mo, pd, situacao):
    atual = estacoes.merge(situacao, on=["codigo_ana", "nome", "rio", "ordem_no_rio"], how="left")
    recente = atual["instante"] >= pd.Timestamp.now(tz="UTC") - pd.Timedelta(days=3)
    tabela_atual = pd.DataFrame(
        {
            "rio": atual["rio"],
            "estação": atual["nome"],
            "cota (m)": (atual["cota_cm"].astype(float) / 100).round(2),
            "24 h (cm)": atual["variacao_24h_cm"].astype(float).round(0),
            "situação": atual["situacao"].map(SITUACOES).where(recente, "⚠️ Sem dados recentes"),
            "última leitura (Manaus)": atual["instante"]
            .dt.tz_convert("America/Manaus")
            .dt.strftime("%d/%m/%Y %H:%M"),
        }
    )
    subindo = int((atual["variacao_24h_cm"].astype(float) > 0)[recente].sum())
    descendo = int((atual["variacao_24h_cm"].astype(float) < 0)[recente].sum())
    mo.vstack(
        [
            mo.md("## Situação atual"),
            mo.hstack(
                [
                    mo.stat(f"{int(recente.sum())} de {len(atual)}", label="Estações com dados"),
                    mo.stat(subindo, label="Subindo (24 h)"),
                    mo.stat(descendo, label="Descendo (24 h)"),
                    mo.stat(
                        int(
                            atual["situacao"]
                            .isin(["alerta", "inundacao", "inundacao_severa", "emergencia_seca"])
                            .sum()
                        ),
                        label="Em alerta",
                    ),
                ],
                justify="start",
                gap=2,
            ),
            mo.ui.table(tabela_atual, selection=None, pagination=False),
        ]
    )
    return


@app.cell
def _(estacoes, mo):
    rio_escolhido = mo.ui.dropdown(
        options=list(dict.fromkeys(estacoes["rio"])), value="Negro", label="Rio"
    )
    periodo = mo.ui.dropdown(
        options={"90 dias": 90, "6 meses": 182, "1 ano": 365, "2 anos": 730},
        value="1 ano",
        label="Período",
    )
    return periodo, rio_escolhido


@app.cell
def _(LOCALE_PT, alt, diarias, mo, pd, periodo, rio_escolhido):
    inicio_periodo = diarias["dia"].max() - pd.Timedelta(days=periodo.value)
    trecho = diarias[(diarias["rio"] == rio_escolhido.value) & (diarias["dia"] >= inicio_periodo)]
    ordem = list(trecho.sort_values("ordem_no_rio")["nome"].drop_duplicates())
    grafico_rio = (
        alt.Chart(trecho)
        .mark_line()
        .encode(
            x=alt.X("dia:T", title=None),
            y=alt.Y("cota_m:Q", title="cota (m)", scale=alt.Scale(zero=False)),
            color=alt.Color("nome:N", sort=ordem, legend=None),
            tooltip=[
                alt.Tooltip("nome:N", title="estação"),
                alt.Tooltip("dia:T", title="dia", format="%d/%m/%Y"),
                alt.Tooltip("cota_m:Q", title="cota (m)", format=".2f"),
            ],
        )
        .properties(height=130, width="container")
        .facet(
            row=alt.Row(
                "nome:N", sort=ordem, title=None, header=alt.Header(labelAngle=0, labelAlign="left")
            )
        )
        .resolve_scale(y="independent")
        .configure(locale=LOCALE_PT)
    )
    mo.vstack(
        [
            mo.md(
                "## Da nascente para a foz\n\n"
                "Estações de um rio, de montante (em cima) para jusante (embaixo). "
                "A cheia e a seca aparecem primeiro nas de cima e chegam semanas depois "
                "às de baixo."
            ),
            mo.hstack([rio_escolhido, periodo], justify="start"),
            mo.ui.altair_chart(grafico_rio, chart_selection=False, legend_selection=False)
            if len(trecho)
            else mo.md("_Sem leituras neste período._"),
        ]
    )
    return


@app.cell
def _(date, diarias, estacoes, mo):
    estacao_escolhida = mo.ui.dropdown(
        options={f"{e.rio} · {e.nome}": e.codigo_ana for e in estacoes.itertuples()},
        value="Negro · Manaus",
        label="Estação",
    )
    anos_disponiveis = sorted(diarias["dia"].dt.year.unique().tolist(), reverse=True)
    padrao = [
        a for a in (date.today().year, date.today().year - 1, 2024, 2021) if a in anos_disponiveis
    ]
    anos = mo.ui.multiselect(
        options=[str(a) for a in anos_disponiveis],
        value=[str(a) for a in dict.fromkeys(padrao)],
        label="Anos",
    )
    return anos, estacao_escolhida


@app.cell
def _(LOCALE_PT, REFERENCIAS, alt, anos, diarias, estacao_escolhida, mo, pd, referencias):
    serie = diarias[
        (diarias["estacao"] == estacao_escolhida.value)
        & diarias["dia"].dt.year.astype(str).isin(anos.value)
    ].assign(
        ano=lambda d: d["dia"].dt.year.astype(str),
        # every year on the same axis (2000 is a leap year, so 29/02 fits)
        dia_do_ano=lambda d: pd.to_datetime("2000-" + d["dia"].dt.strftime("%m-%d")),
    )
    refs = referencias[referencias["estacao"] == estacao_escolhida.value].assign(
        cota_m=lambda d: d["cota_cm"].astype(float) / 100,
        referencia=lambda d: d["tipo"].map(REFERENCIAS),
    )
    linhas_anos = (
        alt.Chart(serie)
        .mark_line()
        .encode(
            x=alt.X("dia_do_ano:T", title=None, axis=alt.Axis(format="%b")),
            y=alt.Y("cota_m:Q", title="cota (m)", scale=alt.Scale(zero=False)),
            color=alt.Color("ano:N", title="ano", sort="descending"),
            tooltip=[
                alt.Tooltip("ano:N"),
                alt.Tooltip("dia:T", title="dia", format="%d/%m/%Y"),
                alt.Tooltip("cota_m:Q", title="cota (m)", format=".2f"),
            ],
        )
    )
    linhas_ref = (
        alt.Chart(refs)
        .mark_rule(strokeDash=[4, 4], color="gray")
        .encode(
            y="cota_m:Q", tooltip=["referencia:N", alt.Tooltip("cota_m:Q", format=".2f"), "fonte:N"]
        )
    )
    a_direita = refs["tipo"].isin(["atencao", "alerta", "emergencia_seca"])
    rotulos_ref = alt.layer(
        alt.Chart(refs[~a_direita])
        .mark_text(align="left", dx=4, dy=-6, color="gray", fontSize=11)
        .encode(y="cota_m:Q", x=alt.value(0), text="referencia:N"),
        alt.Chart(refs[a_direita])
        .mark_text(align="right", dx=-4, dy=-6, color="gray", fontSize=11)
        .encode(y="cota_m:Q", x=alt.value("width"), text="referencia:N"),
    )
    grafico_anos = (linhas_anos + linhas_ref + rotulos_ref).properties(
        height=380, width="container"
    )
    mo.vstack(
        [
            mo.md(
                "## Comparação entre anos\n\n"
                "Cada linha é um ano, no mesmo calendário. Linhas tracejadas: cotas de referência "
                "do SGB. A telemetria começa em 2015; anos sem leituras não aparecem."
            ),
            mo.hstack([estacao_escolhida, anos], justify="start"),
            mo.ui.altair_chart(grafico_anos, chart_selection=False)
            if len(serie)
            else mo.md("_Sem leituras para esta estação nos anos escolhidos._"),
        ]
    )
    return


@app.cell
def _(coletas, mo, pd):
    resumo_coletas = (
        coletas.groupby(["fonte", "status"]).size().unstack(fill_value=0).reset_index()
        if len(coletas)
        else pd.DataFrame()
    )
    log = pd.DataFrame(
        {
            "início (Manaus)": coletas["inicio"]
            .dt.tz_convert("America/Manaus")
            .dt.strftime("%d/%m %H:%M"),
            "fonte": coletas["fonte"],
            "status": coletas["status"],
            "novas": coletas["leituras_novas"],
            "duração (s)": (coletas["fim"] - coletas["inicio"]).dt.total_seconds().round(0),
            "erro": coletas["erro"].fillna("").str.slice(0, 160),
        }
    )
    falhas = coletas["status"].isin(["parcial", "falha"]).sum()
    mo.vstack(
        [
            mo.md("## Coletas (últimos 30 dias)"),
            mo.hstack(
                [
                    mo.stat(len(coletas), label="Execuções"),
                    mo.stat(int(falhas), label="Com falha (parcial ou total)"),
                    mo.stat(
                        coletas["inicio"].max().tz_convert("America/Manaus").strftime("%d/%m %H:%M")
                        if len(coletas)
                        else "—",
                        label="Última coleta (Manaus)",
                    ),
                ],
                justify="start",
                gap=2,
            ),
            mo.ui.table(resumo_coletas, selection=None, pagination=False),
            mo.accordion({"Registro de cada execução": mo.ui.table(log, selection=None)}),
        ]
    )
    return


@app.cell
def _(LOCALE_PT, alt, estacoes, mo, pd, qualidade):
    por_estacao = (
        qualidade.groupby("estacao")[["ok", "corrigidas", "suspeitas"]]
        .sum()
        .reset_index()
        .merge(estacoes, left_on="estacao", right_on="codigo_ana")
        .sort_values(["rio_id", "ordem_no_rio"])
        .reset_index(drop=True)
    )
    tabela_qualidade = pd.DataFrame(
        {
            "rio": por_estacao["rio"],
            "estação": por_estacao["nome"],
            "leituras ok": por_estacao["ok"],
            "corrigidas": por_estacao["corrigidas"],
            "suspeitas": por_estacao["suspeitas"],
            "% suspeitas": (
                100
                * por_estacao["suspeitas"]
                / por_estacao[["ok", "corrigidas", "suspeitas"]].sum(axis=1)
            ).round(3),
        }
    )
    suspeitas_mes = (
        qualidade[qualidade["suspeitas"] > 0]
        .merge(estacoes, left_on="estacao", right_on="codigo_ana")
        .assign(mes=lambda d: pd.to_datetime(d["mes"]))
    )
    grafico_suspeitas = (
        alt.Chart(suspeitas_mes)
        .mark_bar()
        .encode(
            x=alt.X("yearmonth(mes):T", title=None),
            y=alt.Y("sum(suspeitas):Q", title="leituras suspeitas"),
            color=alt.Color("nome:N", title="estação"),
            tooltip=["nome:N", alt.Tooltip("yearmonth(mes):T", title="mês"), "sum(suspeitas):Q"],
        )
        .properties(height=220, width="container")
        .configure(locale=LOCALE_PT)
    )
    mo.vstack(
        [
            mo.md(
                "## Qualidade das leituras\n\n"
                "Suspeitas: saltos isolados ou valores fora da faixa histórica. Ficam guardadas, "
                "mas fora dos gráficos e do bot. Corrigidas: erro de digitação do Porto de Manaus "
                "corrigido pela coluna de variação."
            ),
            mo.ui.table(tabela_qualidade, selection=None, pagination=False),
            mo.ui.altair_chart(grafico_suspeitas, chart_selection=False, legend_selection=False),
        ]
    )
    return


@app.cell
def _(mo):
    mo.md("""
    ---
    Fontes: ANA (telemetria hidrológica), SGB/SACE (cotas de referência), Porto de Manaus.
    Este painel informa; não substitui os alertas oficiais da Defesa Civil e do SGB.
    """)
    return


if __name__ == "__main__":
    app.run()
