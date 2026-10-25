# Rios Amazônicos

Monitor aberto das cotas dos rios Negro, Solimões, Madeira e Amazonas.
Projeto open source para a comunidade amazonense: dados oficiais reunidos,
limpos e explicados num só lugar — painel, histórico e alertas no Telegram.

Requisitos completos, personas, critérios de aceite e riscos: `docs/PRD.md`.
Status das fases: `docs/fases.md`.

## Missão

- Unificar dados hoje espalhados (ANA, SGB, Porto de Manaus) num banco único.
- Mostrar a cheia e a seca "descendo" os rios, de montante para jusante.
- Avisar a população quando uma estação cruza níveis de alerta.
- Ser código de referência: organizado, testado, documentado, reutilizável.

## Rios e estações (versão inicial)

| Rio      | Estação (montante → jusante) | Código ANA |
|----------|------------------------------|------------|
| Negro    | São Gabriel da Cachoeira     | 14320001   |
| Negro    | Barcelos                     | 14480002   |
| Negro    | Manaus                       | 14990000   |
| Solimões | Tabatinga                    | 10100000   |
| Solimões | Coari                        | 13150000   |
| Solimões | Manacapuru                   | 14100000   |
| Madeira  | Porto Velho (RO)             | 15400000   |
| Madeira  | Humaitá                      | 15630000   |
| Amazonas | Itacoatiara                  | 16030000   |
| Amazonas | Parintins                    | 16350002   |

Novas estações entram por cadastro no banco, sem mudar código.
Candidatos futuros: Purus, Juruá, Branco.

## Fontes de dados

1. **ANA – telemetria** (principal): `telemetriaws1.ana.gov.br/ServiceANA.asmx`,
   método `DadosHidrometeorologicos`. Público, XML, nível em **cm**, leituras
   de 15 min a 1 h. Falhas comuns: nível vazio, valores fora da curva.
2. **Porto de Manaus** (conferência de Manaus):
   https://portodemanaus.com.br/nivel-do-rio-negro/ — tabela mensal
   Dia | Cota (m) | Encheu/Vazou (cm), digitada à mão. Problemas conhecidos:
   decimal com ponto ou vírgula; dia repetido/faltando (jun/2026: dois "19",
   nenhum "18"); erro de digitação (06/06/2026: 20.12, correto 28.12).
3. **ANA – HidroWeb** (histórico): séries de décadas; API exige pedir acesso
   (telemetria@ana.gov.br).
4. **SGB – boletins SACE** (referência): cotas de alerta, inundação e
   extremos por estação, cadastradas manualmente.

Uso responsável: no máximo 1 requisição por hora por fonte, User-Agent
identificado com link do repositório.

Referências de Manaus (SGB): máxima 30,02 m (2021) | inundação 27,50 m |
alerta de cheia 27,00 m | inundação severa 29,00 m | risco banho Ponta Negra
16,00 m | mínima 12,13 m (03/11/2024). Cotas das demais estações: `docs/dados.md`.

## Arquitetura

```
ANA telemetria ─┐
Porto de Manaus ┼─► coletor (Python, marimo como script) ─► PostgreSQL "rios"
HidroWeb (carga)┘        de hora em hora, idempotente          │
                                                                ├─► painel marimo (só leitura)
                                                                └─► n8n ◄─► bot Telegram
```

- O coletor é separado do n8n: se a coleta falhar, o bot continua respondendo.
- Coleta idempotente: rodar várias vezes não duplica dados.

## Banco de dados

- Instância compartilhada `pg-projects` (`~/infra/pg-projects`), banco `rios`.
  Host: `127.0.0.1:5432`; containers: `pg-projects:5432` na rede
  `pg-projects-net`. Nunca usar o Postgres interno do n8n.
- Backup diário automático (`pg-projects-backup.timer`).
- Três camadas (schemas), medalhão enxuto:
  - `bruto`: resposta original de cada coleta (XML/HTML), retenção 90 dias.
  - `dados`: `rios`, `estacoes`, `cotas_referencia`, `coletas`, `leituras`,
    `inscritos`. Fonte da verdade.
  - `analise`: views `ultima_leitura`, `leituras_diarias`, `situacao_estacao`,
    `comparativo_anual`. Única camada lida pelo bot e pelo painel.
- Regras: cota sempre em **cm**, fuso America/Manaus; `UNIQUE (estação,
  instante, fonte)` + upsert; cada leitura aponta para sua coleta; qualidade
  `ok`/`suspeita`/`corrigida` + motivo, nunca apagar o valor original; cotas de
  referência são dados (tipo, valor, fonte, data), nunca constantes no código.
- Um usuário por serviço, permissão mínima:
  `rios_coletor` (grava `bruto` e `dados`), `rios_n8n` (lê `analise`, grava
  `inscritos`, marca notificado), `rios_leitura` (só lê `analise`).
- Dicionário de dados: `docs/dados.md` (atualizar junto com qualquer mudança
  de esquema).

## Ambiente (VPS nauraki)

- Ubuntu 24.04 ARM64, acesso só via Tailscale. Nunca abrir portas públicas.
- Python com **uv** (`pyproject.toml` + `uv.lock`); nunca pip.
  Lint/format: `ruff`; tipos: `ty check`; testes: `pytest`.
- n8n: `~/infra/n8n`, editor `http://nauraki:5678`, webhooks HTTPS em
  `https://flow.nauraki.com`. Não alterar sem perguntar.
- marimo: serviço systemd `marimo.service`, porta 2718 (rascunhos). Não alterar sem perguntar.
- marimo do projeto: `rios-marimo.service` (systemd de usuário), `http://nauraki:2719`,
  ambiente do projeto (`uv run`), pasta `coletor/notebooks`. Trabalho ao vivo com
  `marimo pair --url http://127.0.0.1:2719`.

## Estrutura

```
rios-amazonicos/
├── CLAUDE.md            # este arquivo
├── README.md            # vitrine do projeto (GitHub)
├── LICENSE
├── .env.example         # variáveis sem valores
├── .env                 # segredos (chmod 600, nunca no git)
├── .gitignore
├── db/init/             # SQL de esquema, usuários e dados de estações
├── coletor/
│   ├── pyproject.toml
│   ├── rios/            # pacote: fontes (ana, porto), limpeza, banco
│   ├── notebooks/       # coleta.py e painel.py (marimo)
│   └── tests/           # pytest + fixtures (XML da ANA, HTML do Porto)
├── n8n/                 # workflow exportado (JSON) + importar.sh
└── docs/
    ├── PRD.md           # requisitos do produto
    ├── dados.md         # dicionário de dados e cotas de referência
    └── fases.md         # checklist das fases
```

## Fases

- [x] Fase 0: diagnóstico da VPS, estrutura, git
- [x] Fase 1: banco (esquema, usuários, estações, testes de permissão)
- [x] Fase 2: coletores ANA e Porto (baixar e extrair)
- [x] Fase 3: limpeza + testes automatizados dos parsers
- [x] Fase 4: gravação no banco + coleta de hora em hora + carga histórica
- [x] Fase 5: bot Telegram (/start, /nivel <cidade>, /semana, /alertas, /parar)
- [x] Fase 6: boletim diário dos 4 rios com alertas de cota
- [x] Fase 7: painel (rios montante→jusante, comparação entre anos, log de coletas)
- [ ] Fase 8: GitHub (README, CI, screenshots, guia de contribuição)

## Regras de trabalho

- Uma fase por vez. Ao terminar: reportar e PARAR.
- Antes de criar arquivos ou iniciar etapa nova, dizer o próximo passo e
  esperar o ok.
- Perguntar antes de ação destrutiva ou que mexa em serviço existente.
- Segredos só no `.env`; nunca mostrar senhas ou tokens.
- Banco nunca exposto além de `127.0.0.1`.
- Python com type hints; testes e verificações passando antes de concluir fase.
- Um commit por fase, mensagem em português; atualizar `docs/fases.md`.
- Se algo não bater com a realidade, avisar em vez de improvisar.
