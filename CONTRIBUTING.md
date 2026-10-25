# Como contribuir

Obrigado pelo interesse! O projeto é pequeno e quer continuar simples: dados
oficiais confiáveis, código fácil de ler e bem testado.

## Formas de ajudar

- **Avisar sobre dados estranhos**: uma cota que não bate com o boletim do SGB,
  um salto que parece real mas foi marcado como suspeito, uma estação parada.
  Abra uma issue com estação, data e, se possível, o link da fonte oficial.
- **Cotas de referência**: cotas de alerta e inundação de estações que ainda
  não têm (Itacoatiara, Parintins), sempre com a fonte.
- **Estações novas**: Purus, Juruá e Branco estão na fila. Uma estação nova é
  um cadastro em `db/init/03_carga_inicial.sql`, não código novo.
- **Código**: correções, testes e melhorias no painel ou no bot.

## Preparar o ambiente

Requisitos: [uv](https://docs.astral.sh/uv/) e Docker (PostgreSQL 17).

```bash
cp .env.example .env     # preencha; nunca envie o .env
bash db/aplicar.sh       # ver README para PG_CONTAINER / PGHOST
cd coletor
uv sync
```

## Antes de abrir um pull request

```bash
cd coletor
uv run ruff check --fix . && uv run ruff format .
uv run ty check
uv run marimo check notebooks/*.py
uv run pytest
```

O CI roda as mesmas verificações num PostgreSQL vazio com
`coletor/tests/fixtures/dados_ci.sql`. Se um teste precisa de dados, acrescente
o mínimo nesse arquivo.

## Convenções

- **Python** com type hints; dependências só com `uv add` (nada de pip).
- **Nomes** de domínio em português (`cota_cm`, `estacao`, `leituras`),
  comentários e docstrings em inglês, textos para o usuário em português.
- **Cota sempre em centímetros** no banco; fuso `America/Manaus`.
- **Nunca apagar o valor original**: limpeza marca `suspeita` ou `corrigida`
  com motivo.
- **Cotas de referência são dados**, cadastradas no banco com fonte e data,
  nunca constantes no código.
- **Mudou o esquema?** Atualize `docs/dados.md` no mesmo pull request.
- **Fontes oficiais**: no máximo uma requisição por hora por fonte.
- **Segredos** só no `.env`; nunca em código, testes, issues ou logs.
- Commits pequenos, com mensagem curta em português.

## Fixtures de teste

Respostas reais das fontes ficam em `coletor/tests/fixtures/` (XML da ANA, HTML
do Porto). Para um caso novo, salve a resposta original e escreva o teste em
cima dela, sem baixar nada durante os testes.

## Código de conduta

Seja respeitoso e paciente. O projeto é para a comunidade amazonense, e todo
mundo é bem-vindo, de quem mora na beira do rio a quem programa.
