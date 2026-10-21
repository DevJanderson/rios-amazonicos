# Dados — Rios Amazônicos

Dicionário de dados, organização em camadas e cotas de referência.
Atualize este documento junto com qualquer mudança de esquema.

## 1. Camadas

```
fonte ─► bruto ─────────► dados ────────────► analise
         (como chegou)    (limpo, tipado,     (views prontas para
                           com qualidade)      bot e painel)
```

| Schema | Papel | Quem grava | Quem lê |
|---|---|---|---|
| `bruto` | Resposta original de cada coleta, retenção de 90 dias | `rios_coletor` | `rios_coletor` |
| `dados` | Fonte da verdade, limpa e tipada | `rios_coletor` (`inscritos`: `rios_n8n`) | `rios_coletor` |
| `analise` | Views de consumo | — | `rios_n8n`, `rios_leitura` |

## 2. Convenções

- **Cota em centímetros** (inteiro ou decimal), na régua da estação. Metros só na exibição.
- **Datas/horas** em `timestamptz`; exibição no fuso `America/Manaus`.
- Cotas **negativas são válidas**: o zero da régua é arbitrário (ex.: Parintins −2,67 m em 2024).
- **Fontes** (`fonte`): `ana_telemetria`, `porto_manaus`, `ana_hidroweb`.
- **Qualidade** (`qualidade`): `ok`, `suspeita`, `corrigida`, sempre com `motivo` quando ≠ `ok`.
- Nomes de tabelas e colunas em português, minúsculas, `snake_case`.

## 3. Tabelas (planejado — Fase 1)

### `bruto.respostas`
| Coluna | Tipo | Descrição |
|---|---|---|
| id | bigint | Identificador |
| coleta_id | bigint | Coleta que gerou a resposta |
| fonte | text | Origem |
| url | text | URL consultada |
| recebido_em | timestamptz | Momento da resposta |
| status_http | int | Código HTTP |
| conteudo | bytea | Corpo original, comprimido (gzip) |
| versao_parser | text | Versão do parser usada |

### `dados.rios`
| Coluna | Tipo | Descrição |
|---|---|---|
| id | smallint | Identificador |
| nome | text | Negro, Solimões, Madeira, Amazonas |

### `dados.estacoes`
| Coluna | Tipo | Descrição |
|---|---|---|
| codigo_ana | text | Código da estação na ANA (chave) |
| nome | text | Nome da estação |
| municipio | text | Cidade |
| uf | char(2) | Estado |
| rio_id | smallint | Rio |
| ordem_no_rio | smallint | Posição montante → jusante |
| ativa | boolean | Se entra na coleta |

### `dados.cotas_referencia`
| Coluna | Tipo | Descrição |
|---|---|---|
| estacao | text | Código ANA |
| tipo | text | `atencao`, `alerta`, `inundacao`, `inundacao_severa`, `emergencia_seca`, `maxima_historica`, `minima_historica` |
| cota_cm | numeric | Valor em cm |
| data_evento | date | Data do evento (para máximas e mínimas) |
| fonte | text | Documento de origem |
| vigente_desde | date | Quando passou a valer |

### `dados.coletas`
| Coluna | Tipo | Descrição |
|---|---|---|
| id | bigint | Identificador |
| fonte | text | Origem |
| inicio, fim | timestamptz | Duração |
| status | text | `sucesso`, `parcial`, `falha` |
| leituras_novas | int | Leituras inseridas ou atualizadas |
| erro | text | Mensagem, se houver |

### `dados.leituras`
| Coluna | Tipo | Descrição |
|---|---|---|
| estacao | text | Código ANA |
| instante | timestamptz | Momento da medição |
| fonte | text | Origem |
| cota_cm | numeric | Valor após limpeza |
| cota_original | text | Valor como veio da fonte |
| qualidade | text | `ok`, `suspeita`, `corrigida` |
| motivo | text | Motivo da marcação |
| coleta_id | bigint | Coleta de origem |

Chave única: `(estacao, instante, fonte)`.

### `dados.inscritos`
| Coluna | Tipo | Descrição |
|---|---|---|
| chat_id | bigint | Chat do Telegram |
| estacoes | text[] | Estações acompanhadas |
| ativo | boolean | Recebe mensagens |
| criado_em | timestamptz | Inscrição |
| ultimos_alertas | jsonb | Último nível alertado por estação (evita repetir) |

### Views em `analise`
| View | Conteúdo |
|---|---|
| `ultima_leitura` | Leitura mais recente de cada estação, com variação de 24 h |
| `leituras_diarias` | Um valor por estação por dia |
| `situacao_estacao` | Classificação atual: normal, atenção, alerta, inundação, inundação severa, seca |
| `comparativo_anual` | Mesmo dia em anos anteriores e nos anos extremos |

## 4. Estações

| Rio | Ordem | Estação | Código ANA | UF |
|---|---|---|---|---|
| Negro | 1 | São Gabriel da Cachoeira | 14320001 | AM |
| Negro | 2 | Barcelos | 14480002 | AM |
| Negro | 3 | Manaus | 14990000 | AM |
| Solimões | 1 | Tabatinga | 10100000 | AM |
| Solimões | 2 | Coari (Itapéua) | 13150000 | AM |
| Solimões | 3 | Manacapuru | 14100000 | AM |
| Madeira | 1 | Porto Velho | 15400000 | RO |
| Madeira | 2 | Humaitá | 15630000 | AM |
| Amazonas | 1 | Itacoatiara | 16030000 | AM |
| Amazonas | 2 | Parintins | 16350002 | AM |

## 5. Cotas de referência (levantamento de 20/10/2026, em metros)

| Estação | Atenção | Alerta | Inundação | Inund. severa | Máxima histórica | Mínima histórica |
|---|---|---|---|---|---|---|
| Manaus | — | 27,00 | 27,50 | 29,00 | 30,02 (16/06/2021) | 12,13 (03/11/2024) |
| Manacapuru | — | — | — | 19,60 | 20,86 (17/06/2021) | 2,06 (12/10/2024) |
| Itacoatiara | — | — | 14,00 | 14,20 | 15,20 (27/05/2021) | −0,18 (01/11/2024) |
| Parintins | — | — | 8,43 | 9,30 | 9,47 (30/05/2021) | −2,67 (07/11/2024) |
| Porto Velho | 14,00 | 15,00 | 17,00 | — | — | — |
| Humaitá | — | — | — | — | 25,63 (11/04/2014) | 8,02 (15/10/2024) |
| Coari (Itapéua) | — | — | — | — | 18,01 (24/06/2015) | −0,29 (07/10/2024) |
| Tabatinga | — | — | — | — | 13,82 (25/08/1999)¹ | −2,54 (26/09/2024) |
| São Gabriel da Cachoeira | — | — | — | — | 12,68 (11/06/2021) | 3,30 (07/02/1992) |
| Barcelos | — | — | — | — | 10,52 (22/06/2022) | 0,58 (18/03/1980) |

Cota de seca: **Tabatinga — emergência 1,50 m** (SGB, 2026).
Manaus, referência local: risco para banho na Ponta Negra 16,00 m.

¹ Data a conferir na série da ANA (pico costuma ocorrer em abril/maio).

Lacunas: o SGB só publica cotas de alerta/inundação para cidades com histórico
de inundação urbana; as demais estações usam máximas/mínimas históricas e a
faixa de permanência 15–85% como referência de normalidade.

### Fontes
- SGB, 24º Boletim de Alerta Hidrológico da Bacia do Amazonas (16/06/2026):
  https://www.sgb.gov.br/sace/boletins/Amazonas/20260616_17-20260616%20-%20182651.pdf
- SGB, Boletim do rio Madeira (2018) e reportagens com base no SGB para Porto Velho:
  https://www.sgb.gov.br/sace/boletins/Madeira/20180326_15-20180326%20-%20154852.pdf
- Portal Amazônia, alerta de vazante do SGB (2026), Tabatinga:
  https://portalamazonia.com/meio-ambiente/sgb-estiagem-severa-am-2026/
