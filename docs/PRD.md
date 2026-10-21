# PRD — Rios Amazônicos

| Campo | Valor |
|---|---|
| Produto | Rios Amazônicos — monitor aberto das cotas dos rios da Amazônia |
| Autor | Janderson Lira |
| Status | Rascunho aprovado para a Fase 0 |
| Versão | 0.1 |
| Data | 20/10/2026 |
| Licença | MIT (open source) |

---

## 1. Resumo

O Rios Amazônicos coleta, limpa e organiza as cotas (níveis) dos rios Negro,
Solimões, Madeira e Amazonas, publicadas por fontes oficiais, num banco de dados
único com histórico. A partir desse banco, oferece um **painel** com gráficos e
um **bot do Telegram** que responde consultas e envia boletim diário com alertas
quando uma estação cruza níveis críticos.

O projeto é open source e pensado para a comunidade amazonense, e também serve
como portfólio técnico (engenharia de dados, automação e integração).

## 2. Problema

Na Amazônia, o rio dita a vida: transporte, abastecimento, pesca, comércio,
escola e saúde dependem do nível da água. Cheias e secas extremas ficaram mais
frequentes (cheia recorde de 2021 em Manaus com 30,02 m; seca recorde de 2024
com 12,11 m).

Hoje, quem quer acompanhar o nível dos rios enfrenta:

1. **Dados espalhados.** ANA, Serviço Geológico do Brasil (SGB) e Porto de
   Manaus publicam em lugares e formatos diferentes (XML, PDF, tabela HTML).
2. **Dados sujos.** Erros de digitação, decimal com ponto ou vírgula, dias
   repetidos ou faltando, sensores sem leitura.
3. **Visão isolada.** As fontes mostram uma cidade por vez. O nível em Manaus,
   porém, depende do Solimões e do Madeira: a cheia "desce" os rios ao longo de
   semanas, e isso não aparece em lugar nenhum de forma simples.
4. **Pouca acessibilidade.** Os boletins técnicos não chegam a quem mais
   precisa, de forma simples e no celular.

## 3. Por que este projeto

- **Impacto social:** informação confiável e acessível ajuda famílias,
  ribeirinhos, comerciantes, barqueiros e defesa civil a se prepararem.
- **Dado aberto bem tratado:** os dados já são públicos, mas pouco usáveis. O
  valor está em unificar, limpar e explicar.
- **Visão de bacia:** acompanhar montante → jusante permite antecipar o que
  vai acontecer rio abaixo.
- **Código de referência:** um projeto pequeno, bem documentado e testado, que
  outras pessoas possam estudar, reutilizar e estender para outros rios.
- **Portfólio:** demonstra coleta (scraping e API), qualidade de dados, banco
  relacional com segurança, automação (n8n), bot e visualização.

## 4. Objetivos e não objetivos

### Objetivos

- O1. Coletar automaticamente, de hora em hora, as cotas de 10 estações em 4 rios.
- O2. Guardar histórico limpo e confiável, sem duplicações, com origem rastreável.
- O3. Disponibilizar painel com situação atual, evolução e comparação entre anos.
- O4. Oferecer bot no Telegram com consultas por cidade, boletim diário e alertas.
- O5. Publicar o projeto no GitHub com documentação, testes e CI.

### Não objetivos (nesta versão)

- Previsão hidrológica ou modelos de machine learning.
- Aplicativo móvel nativo ou site público próprio.
- Substituir alertas oficiais da Defesa Civil ou do SGB (o projeto informa e
  cita as fontes oficiais).
- Cobrir todos os rios da bacia (Purus, Juruá e Branco ficam para depois).

## 5. Público e personas

| Persona | Necessidade | Como o produto atende |
|---|---|---|
| Morador de Manaus | Saber se o rio está subindo ou descendo e se há risco | `/nivel manaus`, boletim diário |
| Ribeirinho / barqueiro no interior | Nível da sua cidade e tendência | `/nivel <cidade>`, alertas por estação |
| Comerciante / logística fluvial | Planejar transporte na seca e na cheia | Painel com tendência e comparação entre anos |
| Jornalista / estudante / pesquisador | Dados históricos limpos | Painel e dados consultáveis |
| Desenvolvedor da comunidade | Reutilizar ou contribuir | Código aberto, testes e documentação |

## 6. Histórias de usuário

- Como morador, quero mandar `/nivel manaus` e receber a cota atual, a variação
  do dia e a comparação com o ano passado.
- Como ribeirinho, quero escolher as estações que acompanho e receber alerta
  quando uma delas passar da cota de alerta.
- Como inscrito, quero receber todo dia um boletim curto com os 4 rios.
- Como inscrito, quero mandar `/parar` e deixar de receber mensagens.
- Como analista, quero ver no painel as estações de um rio da nascente para a
  foz e perceber a cheia "descendo".
- Como analista, quero comparar o ano atual com anos extremos (2021, 2024).
- Como mantenedor, quero ver o log de coletas e saber quando uma fonte falhou.
- Como desenvolvedor, quero adicionar uma estação nova só cadastrando no banco.

## 7. Escopo: rios e estações (versão inicial)

| Rio | Estação (montante → jusante) | Código ANA |
|---|---|---|
| Negro | São Gabriel da Cachoeira | 14320001 |
| Negro | Barcelos | 14480002 |
| Negro | Manaus | 14990000 |
| Solimões | Tabatinga | 10100000 |
| Solimões | Coari | 13150000 |
| Solimões | Manacapuru | 14100000 |
| Madeira | Porto Velho (RO) | 15400000 |
| Madeira | Humaitá | 15630000 |
| Amazonas | Itacoatiara | 16030000 |
| Amazonas | Parintins | 16350002 |

**Por que esses rios:** o Negro e o Solimões se encontram em Manaus e formam o
Amazonas; o Madeira, maior afluente da margem direita, deságua entre Manaus e
Itacoatiara e influencia diretamente Itacoatiara e Parintins.

## 8. Fontes de dados

| Fonte | Uso | Formato | Frequência | Observações |
|---|---|---|---|---|
| ANA – telemetria (`ServiceANA.asmx`, `DadosHidrometeorologicos`) | Principal, todas as estações | XML, nível em cm | 15 min a 1 h | Público; falhas de sensor (nível vazio, valores fora da curva) |
| Porto de Manaus | Conferência de Manaus | Tabela HTML mensal | Diária | Digitado à mão; erros conhecidos (ver 9.2) |
| ANA – HidroWeb | Carga histórica | API/CSV | Sob demanda | API exige pedir acesso (telemetria@ana.gov.br) |
| SGB – boletins SACE | Cotas de referência por estação | PDF | Semanal | Cadastro manual de alerta, inundação e extremos |

**Uso responsável:** no máximo 1 requisição por hora por fonte, User-Agent
identificado com link do repositório, e citação das fontes no painel e no bot.

## 9. Requisitos funcionais

### 9.1 Coleta

- RF01. Coletar as leituras de todas as estações ativas na ANA de hora em hora.
- RF02. Coletar a tabela do Porto de Manaus para conferência.
- RF03. Coleta idempotente: rodar várias vezes não duplica leituras.
- RF04. Registrar cada execução (início, fim, fonte, nº de leituras, erro) em `coletas`.
- RF05. Falha de uma fonte ou estação não interrompe as demais.

### 9.2 Limpeza e qualidade

- RF06. Normalizar decimal com ponto ou vírgula.
- RF07. Tratar dia repetido e dia faltando (ex.: jun/2026 no Porto: dois "19" e nenhum "18").
- RF08. Detectar valores fora da curva (ex.: 06/06/2026 publicado 20.12, correto 28.12)
  e marcar como suspeitos, sem apagar o dado bruto.
- RF09. Padronizar unidade (cota guardada em cm) e fuso (America/Manaus).
- RF10. Guardar a fonte de cada leitura.

### 9.3 Banco

- RF11. Cadastro de rios e estações, com ordem no rio e cotas de referência.
- RF12. Nova estação entra por cadastro, sem mudança de código.
- RF13. Visão com um valor por estação por dia, para o bot e o painel.

### 9.4 Bot do Telegram (via n8n)

- RF14. `/start`: inscreve e explica o uso.
- RF15. `/nivel <cidade>`: cota atual, variação de 24 h e situação frente às referências.
- RF16. `/semana <cidade>`: evolução dos últimos 7 dias.
- RF17. `/alertas`: escolher estações acompanhadas.
- RF18. `/parar`: cancela a inscrição.
- RF19. Boletim diário com os 4 rios para os inscritos.
- RF20. Alerta quando uma estação acompanhada cruza uma cota de referência,
  sem repetir o mesmo alerta.

### 9.5 Painel (marimo)

- RF21. Situação atual de todas as estações.
- RF22. Visão montante → jusante por rio.
- RF23. Comparação do ano atual com anos anteriores e extremos.
- RF24. Log de coletas e indicadores de qualidade (leituras suspeitas, falhas).

## 10. Requisitos não funcionais

| Código | Categoria | Requisito |
|---|---|---|
| RNF01 | Segurança | Segredos só no `.env` (chmod 600), nunca no git. |
| RNF02 | Segurança | Banco acessível só em `127.0.0.1` e na rede Docker interna. |
| RNF03 | Segurança | Um usuário de banco por serviço, com permissão mínima. |
| RNF04 | Confiabilidade | O bot funciona mesmo se a coleta falhar. |
| RNF05 | Confiabilidade | Backup diário do banco, com restauração testada. |
| RNF06 | Qualidade | Python com type hints, `ruff` e `ty check` sem erros. |
| RNF07 | Qualidade | Testes automatizados dos parsers com fixtures reais. |
| RNF08 | Ética | Respeito às fontes: limite de requisições e citação. |
| RNF09 | Manutenibilidade | Documentação em português; código e commits padronizados. |
| RNF10 | Portabilidade | Roda em ARM64; dependências gerenciadas com uv. |

## 11. Arquitetura

```
ANA telemetria ─┐
Porto de Manaus ┼─► coletor (Python, marimo como script) ─► PostgreSQL "rios"
HidroWeb (carga)┘        de hora em hora, idempotente          │
                                                                ├─► painel marimo (só leitura)
                                                                └─► n8n ◄─► bot Telegram
```

| Componente | Tecnologia | Responsabilidade |
|---|---|---|
| Coletor | Python + marimo (notebook rodado como script), uv | Baixar, limpar e gravar |
| Banco | PostgreSQL 17 (instância `pg-projects`) | Histórico e regras de unicidade |
| Automação | n8n (já existente) | Bot, boletim e alertas |
| Interface | Telegram | Consulta e notificações |
| Painel | marimo | Visualização e auditoria |

### Modelo de dados (conceitual)

- `rios` (id, nome)
- `estacoes` (código ANA, cidade, UF, rio, ordem no rio, cotas de referência, ativa)
- `leituras` (estação, data/hora, cota em cm, fonte, suspeita) — única por estação + instante + fonte
- `coletas` (início, fim, fonte, status, nº de leituras, erro)
- `inscritos` (chat do Telegram, estações acompanhadas, ativo, últimos alertas enviados)
- `leituras_diarias` (visão: 1 valor por estação por dia)

Usuários do banco: `coletor` (grava), `n8n_rios` (lê + inscritos + marca
notificado), `painel` (só lê).

## 12. Metodologia

- **Entregas incrementais por fases.** Cada fase tem escopo fechado, critério
  de aceite, testes passando, atualização de `docs/fases.md` e um commit.
  Uma fase só começa após aprovação explícita.
- **Dados primeiro.** Banco e qualidade dos dados vêm antes das interfaces: bot
  e painel só são tão bons quanto o dado.
- **Dado bruto preservado.** Limpeza marca e corrige, mas nunca destrói a
  origem; tudo é rastreável até a fonte.
- **Testes com casos reais.** Os erros já encontrados nas fontes viram fixtures
  e testes automatizados.
- **Exploração no notebook, código no pacote.** O marimo é usado para explorar
  e demonstrar; a lógica reutilizável vive no pacote `rios/`, testável.
- **Segurança por padrão.** Menor privilégio, segredos fora do código e nada
  exposto à internet além dos webhooks do n8n.
- **Documentação viva.** `CLAUDE.md`, este PRD e `docs/fases.md` são atualizados
  ao longo do projeto.

## 13. Roadmap e critérios de aceite

| Fase | Entrega | Critério de aceite |
|---|---|---|
| 0 | Diagnóstico da VPS, estrutura, git, PRD | Estrutura criada, documentos revisados, primeiro commit |
| 1 | Banco: esquema, usuários, estações, testes de permissão | Cada usuário só consegue o que deve; 10 estações cadastradas; backup inclui o banco |
| 2 | Coletores ANA e Porto (baixar e extrair) | Notebook baixa e extrai as 10 estações e a tabela do Porto |
| 3 | Limpeza + testes dos parsers | Todos os casos conhecidos cobertos por testes que passam |
| 4 | Gravação + coleta de hora em hora + carga histórica | Coleta agendada, idempotente, com log; histórico carregado |
| 5 | Bot Telegram | Comandos respondem corretamente com dados reais |
| 6 | Boletim diário e alertas | Boletim chega no horário; alerta dispara uma vez por cruzamento |
| 7 | Painel | Gráficos atual, montante → jusante, entre anos e log de coletas |
| 8 | GitHub | README, CI com testes, screenshots, guia de contribuição |

## 14. Métricas de sucesso

- Coleta: ≥ 95% das execuções horárias com sucesso em 30 dias.
- Atualidade: última leitura de cada estação ativa com menos de 3 h.
- Qualidade: 100% dos casos de erro conhecidos detectados pelos testes.
- Bot: resposta a comandos em menos de 5 s.
- Comunidade: repositório público com README completo, CI verde e primeiras
  contribuições ou usos externos.

## 15. Riscos e mitigação

| Risco | Impacto | Mitigação |
|---|---|---|
| Fonte muda formato ou sai do ar | Coleta para | Parsers testados, log de falhas, fontes independentes |
| Sensor da ANA sem leitura ou com valor errado | Dado incorreto | Marcar suspeito, conferir com Porto, nunca apagar bruto |
| Bloqueio por excesso de requisições | Perda de acesso | 1 req/h por fonte, User-Agent identificado |
| Acesso ao HidroWeb negado ou demorado | Sem histórico longo | Começar com telemetria; histórico entra quando liberado |
| Falha da VPS | Perda de dados | Backup diário; backup fora da VPS (pendente) |
| Alerta interpretado como oficial | Risco à população | Mensagens citam a fonte e indicam canais oficiais |
| Vazamento de segredos | Segurança | `.env` fora do git, usuários com menor privilégio |

## 16. Premissas e dependências

- A telemetria da ANA continua pública e sem autenticação.
- O n8n segue com HTTPS público para webhooks do Telegram (`flow.nauraki.com`).
- A instância `pg-projects` e o marimo seguem disponíveis na VPS.
- Cotas de referência por estação serão obtidas dos boletins do SGB.

## 17. Questões em aberto

- Cotas de referência de cada uma das 10 estações (levantar nos boletins do SGB).
- Leitura de Parintins (10 cm em 20/10/2026) e Tabatinga sem nível: validar.
- Horário do boletim diário.
- Pedido de acesso à API do HidroWeb.
- Destino do backup fora da VPS.

## 18. Glossário

- **Cota:** nível da água medido numa régua da estação, em metros ou centímetros.
- **Montante / jusante:** rio acima / rio abaixo.
- **Estação fluviométrica:** ponto de medição do nível de um rio.
- **Telemetria:** envio automático das leituras por sensor.
- **Idempotente:** pode rodar várias vezes com o mesmo resultado, sem duplicar.
- **ANA:** Agência Nacional de Águas e Saneamento Básico.
- **SGB:** Serviço Geológico do Brasil (antiga CPRM).
- **SACE:** Sistema de Alerta de Eventos Críticos do SGB.
