# Fases do projeto

| Fase | Descrição | Status |
|---|---|---|
| 0 | Diagnóstico da VPS, estrutura, PRD, git | ✅ Concluída (20/10/2026) |
| 1 | Banco: esquema, usuários, estações, testes de permissão | ✅ Concluída (20/10/2026) |
| 2 | Coletores ANA e Porto (baixar e extrair) | ⬜ Pendente |
| 3 | Limpeza + testes automatizados dos parsers | ⬜ Pendente |
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
