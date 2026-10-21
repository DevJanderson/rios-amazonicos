# Fases do projeto

| Fase | Descrição | Status |
|---|---|---|
| 0 | Diagnóstico da VPS, estrutura, PRD, git | ✅ Concluída (20/10/2026) |
| 1 | Banco: esquema, usuários, estações, testes de permissão | ✅ Concluída (20/10/2026) |
| 2 | Coletores ANA e Porto (baixar e extrair) | ✅ Concluída (20/10/2026) |
| 3 | Limpeza + testes automatizados dos parsers | ✅ Concluída (20/10/2026) |
| 4 | Gravação no banco + coleta de hora em hora + carga histórica | ⬜ Pendente |
| 5 | Bot Telegram (/start, /nivel, /semana, /alertas, /parar) | ⬜ Pendente |
| 6 | Boletim diário dos 4 rios com alertas de cota | ⬜ Pendente |
| 7 | Painel marimo (montante→jusante, comparação entre anos, log) | ⬜ Pendente |
| 8 | GitHub (README final, CI, screenshots, contribuição) | ⬜ Pendente |

## Fase 0 — registro

- VPS: Ubuntu 24.04 ARM64, 2 vCPU, 11 GB RAM, 165 GB livres.
- n8n 2.44.4 (Docker, Postgres interno), editor `http://nauraki:5678`, webhooks
  HTTPS em `https://flow.nauraki.com`.
- marimo 0.25.2 no host (Python 3.14), `marimo.service`, porta 2718, só Tailscale.
- Postgres de projetos: `pg-projects` (17.11), `127.0.0.1:5432`, backup diário.
- Ferramentas: git 2.43, uv 0.12, Python 3.12/3.13/3.14.
- Escopo ampliado de "Cota do Rio Negro" para 4 rios e 10 estações (ver PRD).

## Fase 1 — registro

- Banco `rios` no `pg-projects`, com schemas `bruto`, `dados` e `analise`.
- Usuários `rios_coletor`, `rios_n8n` e `rios_leitura` (prefixo `rios_` porque a
  instância é compartilhada); senhas só no `.env`.
- SQL em `db/init/` (idempotente), aplicado com `db/aplicar.sh`.
- Carga inicial: 4 rios, 10 estações, cotas de referência do SGB.
- 28 testes (`coletor/tests/test_banco.py`): carga, permissões de cada usuário,
  upsert idempotente, classificação de situação, leituras suspeitas fora das views.
- Backup diário do `pg-projects` já inclui o banco `rios` (conferido).

## Fase 2 — registro

- Pacote `rios.fontes`: `http` (User-Agent identificado, timeout 90 s), `ana`
  (XML da telemetria) e `porto` (tabelas mensais do Porto de Manaus). Extração
  devolve os valores **como publicados** (texto); a limpeza fica para a Fase 3.
- `rios.banco` lê as estações ativas do banco (usuário `rios_coletor`); nada é gravado.
- Notebook `coletor/notebooks/coleta.py`: no editor coleta só ao clicar; como
  script (`uv run python notebooks/coleta.py`) coleta direto e imprime resumo.
- Coleta real em 20/10/2026: 8 de 10 estações ok, Itacoatiara e Parintins com
  HTTP 504 (ANA instável), sem interromper as demais; São Gabriel e Coari sem
  nível no período; Porto: 173 linhas (mai–out/2026).
- Fixtures reais: HTML do Porto (com os erros conhecidos de junho), XML da ANA
  de Manaus (88 leituras) e página 504; um XML sintético cobre nível vazio.
- 36 testes passando (28 do banco + 8 de extração).

## Fase 3 — registro

- `coletor/rios/limpeza.py`: cota em cm (Decimal), fusos (ANA em horário de
  Brasília, Porto às 00:00 de Manaus), qualidade `ok`/`corrigida`/`suspeita`
  com motivo, valor publicado sempre preservado. Regras em `docs/dados.md` §3.
- Casos reais do Porto resolvidos automaticamente: 06/06/2026 publicado 20.12 →
  28.12 (confirmado pela coluna Encheu/Vazou e pelo dia seguinte); "19" repetido
  → dia 18.
- 57 testes passando (+21 de limpeza, com as amostras reais e casos montados).
- Notebook `coleta.py` refeito com a skill `marimo-notebook`: origem
  "Amostras salvas" (sem internet) ou "Ao vivo" (botão), indicadores de
  qualidade, abas (situação atual, correções e suspeitas, Porto, coleta) e
  conferência Porto × ANA em Manaus.
- Coleta real (20/10/2026): 10 de 10 estações ok, 1.278 leituras limpas
  (1.276 ok, 2 corrigidas).
