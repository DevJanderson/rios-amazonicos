# Fases do projeto

| Fase | Descrição | Status |
|---|---|---|
| 0 | Diagnóstico da VPS, estrutura, PRD, git | ✅ Concluída (20/10/2026) |
| 1 | Banco: esquema, usuários, estações, testes de permissão | ✅ Concluída (20/10/2026) |
| 2 | Coletores ANA e Porto (baixar e extrair) | ✅ Concluída (20/10/2026) |
| 3 | Limpeza + testes automatizados dos parsers | ✅ Concluída (20/10/2026) |
| 4 | Gravação no banco + coleta de hora em hora + carga histórica | ✅ Concluída (21/10/2026) |
| 5 | Bot Telegram (/start, /nivel, /semana, /alertas, /parar) | ✅ Concluída (21/10/2026) |
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

## Fase 4 — registro

- `rios/banco.py`: abre/fecha a coleta, guarda a resposta original (gzip) em
  `bruto.respostas`, faz upsert das leituras (conta só linhas novas ou alteradas)
  e apaga respostas brutas com mais de 90 dias.
- `rios/coleta.py`: uma coleta por fonte; consultas à ANA em blocos de até 31
  dias, gravação estação por estação; falha isolada → status `parcial`.
- Notebook `coleta.py` com o padrão da skill `marimo-batch`: os mesmos
  parâmetros pelo formulário (editor, "Gravar no banco" desmarcado por padrão)
  ou pela linha de comando (`-- --help`).
- Agendamento: `deploy/systemd/rios-coleta.timer` de hora em hora (atraso
  aleatório de até 5 min), instalado com `deploy/instalar.sh`. Unidades
  versionadas no repositório e ligadas por symlink.
- Primeira coleta real gravada (20/10/2026): ANA 1.105 leituras, Porto 173;
  repetir não gravou nada novo. Banco com 8,7 MB.
- 67 testes passando (+10 de coleta com HTTP falso e banco real, sem deixar dados).
- Carga histórica (21/10/2026, 08:02–10:18): ANA de 01/01/2015 até hoje, todas
  as leituras, pausa de 5 s, 1.400 consultas, 0 falhas. 1.918.971 leituras
  gravadas (672 suspeitas, 531 delas em Humaitá). Banco com 459 MB.
- Leituras por estação: Manaus 392 mil, Porto Velho 390 mil, Itacoatiara 368 mil,
  Manacapuru 306 mil, Humaitá 208 mil, Barcelos 148 mil, Tabatinga 101 mil.
- Telemetria quase vazia: Parintins (3,5 mil, desde 07/2020), Coari (2,1 mil,
  09/2020–11/2024) e São Gabriel da Cachoeira (1,4 mil, 08/2020–11/2023).
- Mínima de Manaus na telemetria: 12,11 m (a referência oficial é 12,13 m).

## Fase 5 — registro

- Regra do bot no banco (`db/init/04_bot.sql`, schema `bot`, só `rios_n8n`
  executa): `responder`, `boletim`, `alertas_pendentes`, `marcar_alerta`,
  `inscritos_ativos`. Busca de cidade sem acento e por prefixo; estação sem
  leitura há mais de 3 dias aparece como "sem dados recentes".
- n8n: um workflow só, `n8n/rios-amazonicos.json` ("Rios Amazônicos — bot,
  boletim e alertas"), com três gatilhos: mensagem do Telegram, boletim diário
  às 7h30 (Manaus) e alertas de hora em hora (:20). Importado com
  `n8n/importar.sh` (credenciais a partir do `.env`, sem expor segredos).
- Infra: containers do n8n renomeados (`n8n-app`, `n8n-postgres`); `n8n-app` na
  rede `pg-projects-net`. Cloudflare Tunnel separado em `~/infra/cloudflared`
  (`cloudflared-tunnel`, rede `cloudflared-net`), compartilhado entre projetos;
  rota `flow.nauraki.com` → `http://n8n-app:5678`.
- Telegram: o gatilho só funciona com o workflow publicado (o modo de teste do
  n8n usa a URL http da Tailscale, que o Telegram recusa).
- Teste real (21/10/2026): `/start` respondido, inscrição gravada.
- 93 testes passando (+26 do bot).
- Boletim e alertas (Fase 6) já estão no workflow; falta validar o primeiro
  envio real e ajustar o texto se preciso.

