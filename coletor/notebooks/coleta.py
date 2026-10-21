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

    Baixa as fontes e extrai as leituras **como foram publicadas** (sem limpeza).
    Nada é gravado no banco nesta etapa.

    - **ANA, telemetria**: nível em cm, uma consulta por estação ativa.
    - **Porto de Manaus**: tabela mensal Dia | Cota (m) | Encheu/Vazou (cm).

    Uso responsável: no máximo 1 coleta por hora por fonte. No editor, a coleta só
    roda ao clicar no botão; como script (`python coleta.py`), roda direto.
    """)
    return


@app.cell
def _(mo):
    botao = mo.ui.run_button(label="Coletar agora")
    botao
    return (botao,)


@app.cell
def _(botao, mo):
    como_script = mo.app_meta().mode == "script"
    mo.stop(not (botao.value or como_script), mo.md("_Clique em **Coletar agora**._"))
    return


@app.cell
def _():
    from datetime import date, timedelta

    import httpx

    from rios.banco import conectar_coletor, estacoes_ativas
    from rios.fontes import ana, porto
    from rios.fontes.http import TIMEOUT_SECONDS, USER_AGENT, baixar

    with conectar_coletor() as conn:
        estacoes = estacoes_ativas(conn)

    hoje = date.today()
    inicio = hoje - timedelta(days=1)
    cliente = httpx.Client(headers={"User-Agent": USER_AGENT}, timeout=TIMEOUT_SECONDS)
    return ana, baixar, cliente, estacoes, hoje, inicio, porto


@app.cell
def _(ana, baixar, cliente, estacoes, hoje, inicio):
    leituras_ana = []
    resumo_ana = []
    for estacao in estacoes:
        url = ana.url_dados(estacao.codigo_ana, inicio, hoje)
        try:
            resposta = baixar(url, cliente)
            if not resposta.ok:
                raise ana.RespostaAnaInvalida(f"HTTP {resposta.status_http}")
            extraidas = ana.extrair(resposta.conteudo)
            com_nivel = [leitura for leitura in extraidas if leitura.nivel is not None]
            leituras_ana.extend(extraidas)
            resumo_ana.append(
                {
                    "rio": estacao.rio,
                    "estação": estacao.nome,
                    "status": "ok",
                    "registros": len(extraidas),
                    "com nível": len(com_nivel),
                    "último nível (cm)": com_nivel[0].nivel if com_nivel else None,
                    "último horário": com_nivel[0].data_hora if com_nivel else None,
                }
            )
        except Exception as erro:  # one station failing must not stop the others
            resumo_ana.append(
                {"rio": estacao.rio, "estação": estacao.nome, "status": f"falha: {erro}"}
            )
    return leituras_ana, resumo_ana


@app.cell
def _(mo, resumo_ana):
    mo.vstack([mo.md("## ANA — resumo por estação"), mo.ui.table(resumo_ana, selection=None)])
    return


@app.cell
def _(baixar, cliente, porto):
    try:
        resposta_porto = baixar(porto.URL, cliente)
        linhas_porto = porto.extrair(resposta_porto.conteudo) if resposta_porto.ok else []
        erro_porto = None if resposta_porto.ok else f"HTTP {resposta_porto.status_http}"
    except Exception as erro:
        linhas_porto, erro_porto = [], str(erro)
    return erro_porto, linhas_porto


@app.cell
def _(erro_porto, linhas_porto, mo):
    _tabela = [
        {
            "ano": linha.ano,
            "mês": linha.mes,
            "dia": linha.dia,
            "cota (m)": linha.cota_m,
            "variação (cm)": linha.variacao_cm,
        }
        for linha in linhas_porto
    ]
    mo.vstack(
        [
            mo.md("## Porto de Manaus — linhas extraídas"),
            mo.md(f"**Falha:** {erro_porto}") if erro_porto else mo.md(f"{len(_tabela)} linhas."),
            mo.ui.table(_tabela, selection=None),
        ]
    )
    return


@app.cell
def _(leituras_ana, mo):
    mo.vstack(
        [
            mo.md("## ANA — todas as leituras extraídas"),
            mo.ui.table(
                [
                    {
                        "estação": leitura.codigo_estacao,
                        "data/hora": leitura.data_hora,
                        "nível (cm)": leitura.nivel,
                    }
                    for leitura in leituras_ana
                ],
                selection=None,
            ),
        ]
    )
    return


@app.cell
def _(erro_porto, linhas_porto, mo, resumo_ana):
    # Plain-text summary for script runs (cron/systemd logs)
    if mo.app_meta().mode == "script":
        for _linha in resumo_ana:
            print(f"ANA {_linha['estação']}: {_linha['status']} {_linha.get('último nível (cm)')}")
        print(f"Porto: {erro_porto or 'ok'}, {len(linhas_porto)} linhas")
    return


if __name__ == "__main__":
    app.run()
