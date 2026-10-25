-- Esquema em 3 camadas: bruto -> dados -> analise. Roda no banco "rios".
-- Idempotente. Dicionário de dados: docs/dados.md.

REVOKE CREATE ON SCHEMA public FROM PUBLIC;

CREATE SCHEMA IF NOT EXISTS bruto;
CREATE SCHEMA IF NOT EXISTS dados;
CREATE SCHEMA IF NOT EXISTS analise;

-- ---------------------------------------------------------------- dados

CREATE TABLE IF NOT EXISTS dados.rios (
    id   smallint PRIMARY KEY,
    nome text NOT NULL UNIQUE
);

CREATE TABLE IF NOT EXISTS dados.estacoes (
    codigo_ana   text PRIMARY KEY,
    nome         text NOT NULL,
    municipio    text NOT NULL,
    uf           char(2) NOT NULL,
    rio_id       smallint NOT NULL REFERENCES dados.rios (id),
    ordem_no_rio smallint NOT NULL,
    ativa        boolean NOT NULL DEFAULT true,
    UNIQUE (rio_id, ordem_no_rio)
);

CREATE TABLE IF NOT EXISTS dados.cotas_referencia (
    estacao       text NOT NULL REFERENCES dados.estacoes (codigo_ana),
    tipo          text NOT NULL CHECK (tipo IN (
                      'atencao', 'alerta', 'inundacao', 'inundacao_severa',
                      'emergencia_seca', 'maxima_historica', 'minima_historica')),
    cota_cm       numeric(7, 2) NOT NULL,
    data_evento   date,
    fonte         text NOT NULL,
    vigente_desde date NOT NULL,
    PRIMARY KEY (estacao, tipo, vigente_desde)
);

CREATE TABLE IF NOT EXISTS dados.coletas (
    id             bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    fonte          text NOT NULL CHECK (fonte IN ('ana_telemetria', 'porto_manaus', 'ana_hidroweb')),
    inicio         timestamptz NOT NULL DEFAULT now(),
    fim            timestamptz,
    status         text NOT NULL DEFAULT 'em_andamento'
                       CHECK (status IN ('em_andamento', 'sucesso', 'parcial', 'falha')),
    leituras_novas integer NOT NULL DEFAULT 0,
    erro           text
);

CREATE TABLE IF NOT EXISTS dados.leituras (
    estacao       text NOT NULL REFERENCES dados.estacoes (codigo_ana),
    instante      timestamptz NOT NULL,
    fonte         text NOT NULL CHECK (fonte IN ('ana_telemetria', 'porto_manaus', 'ana_hidroweb')),
    cota_cm       numeric(7, 2),
    cota_original text,
    qualidade     text NOT NULL DEFAULT 'ok' CHECK (qualidade IN ('ok', 'suspeita', 'corrigida')),
    motivo        text,
    coleta_id     bigint REFERENCES dados.coletas (id),
    atualizado_em timestamptz NOT NULL DEFAULT now(),
    PRIMARY KEY (estacao, instante, fonte),
    CHECK (qualidade = 'ok' OR motivo IS NOT NULL)
);

CREATE INDEX IF NOT EXISTS leituras_instante_idx ON dados.leituras (instante);

CREATE TABLE IF NOT EXISTS dados.inscritos (
    chat_id         bigint PRIMARY KEY,
    estacoes        text[] NOT NULL DEFAULT '{}',
    ativo           boolean NOT NULL DEFAULT true,
    criado_em       timestamptz NOT NULL DEFAULT now(),
    ultimos_alertas jsonb NOT NULL DEFAULT '{}'
);

-- ---------------------------------------------------------------- bruto

CREATE TABLE IF NOT EXISTS bruto.respostas (
    id            bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    coleta_id     bigint NOT NULL REFERENCES dados.coletas (id),
    fonte         text NOT NULL,
    url           text NOT NULL,
    recebido_em   timestamptz NOT NULL DEFAULT now(),
    status_http   integer,
    conteudo      bytea,
    versao_parser text
);

CREATE INDEX IF NOT EXISTS respostas_recebido_em_idx ON bruto.respostas (recebido_em);

-- ---------------------------------------------------------------- analise
-- Leituras suspeitas ficam fora das views de consumo.

CREATE OR REPLACE VIEW analise.estacoes AS
SELECT e.codigo_ana, e.nome, e.municipio, e.uf, r.nome AS rio, e.ordem_no_rio, e.ativa,
       e.rio_id
FROM dados.estacoes e
JOIN dados.rios r ON r.id = e.rio_id;

CREATE OR REPLACE VIEW analise.cotas_vigentes AS
SELECT DISTINCT ON (estacao, tipo)
       estacao, tipo, cota_cm, data_evento, fonte, vigente_desde
FROM dados.cotas_referencia
WHERE vigente_desde <= current_date
ORDER BY estacao, tipo, vigente_desde DESC;

CREATE OR REPLACE VIEW analise.ultima_leitura AS
SELECT e.codigo_ana, e.nome, e.rio, e.ordem_no_rio,
       u.instante, u.fonte, u.cota_cm,
       u.cota_cm - a.cota_cm AS variacao_24h_cm
FROM analise.estacoes e
JOIN LATERAL (
    SELECT l.instante, l.fonte, l.cota_cm
    FROM dados.leituras l
    WHERE l.estacao = e.codigo_ana AND l.qualidade <> 'suspeita' AND l.cota_cm IS NOT NULL
    ORDER BY l.instante DESC
    LIMIT 1
) u ON true
LEFT JOIN LATERAL (
    SELECT l.cota_cm
    FROM dados.leituras l
    WHERE l.estacao = e.codigo_ana AND l.qualidade <> 'suspeita' AND l.cota_cm IS NOT NULL
      AND l.instante <= u.instante - interval '24 hours'
    ORDER BY l.instante DESC
    LIMIT 1
) a ON true;

CREATE OR REPLACE VIEW analise.leituras_diarias AS
SELECT DISTINCT ON (l.estacao, dia)
       l.estacao,
       (l.instante AT TIME ZONE 'America/Manaus')::date AS dia,
       l.cota_cm,
       l.instante AS ultima_medicao,
       l.fonte
FROM dados.leituras l
CROSS JOIN LATERAL (SELECT (l.instante AT TIME ZONE 'America/Manaus')::date AS dia) d
WHERE l.qualidade <> 'suspeita' AND l.cota_cm IS NOT NULL
ORDER BY l.estacao, dia, l.instante DESC;

CREATE OR REPLACE VIEW analise.situacao_estacao AS
WITH ref AS (
    SELECT estacao,
           max(cota_cm) FILTER (WHERE tipo = 'atencao')          AS atencao,
           max(cota_cm) FILTER (WHERE tipo = 'alerta')           AS alerta,
           max(cota_cm) FILTER (WHERE tipo = 'inundacao')        AS inundacao,
           max(cota_cm) FILTER (WHERE tipo = 'inundacao_severa') AS inundacao_severa,
           max(cota_cm) FILTER (WHERE tipo = 'emergencia_seca')  AS emergencia_seca
    FROM analise.cotas_vigentes
    GROUP BY estacao
)
SELECT u.codigo_ana, u.nome, u.rio, u.ordem_no_rio, u.instante, u.cota_cm, u.variacao_24h_cm,
       CASE
           WHEN u.cota_cm >= r.inundacao_severa THEN 'inundacao_severa'
           WHEN u.cota_cm >= r.inundacao        THEN 'inundacao'
           WHEN u.cota_cm >= r.alerta           THEN 'alerta'
           WHEN u.cota_cm >= r.atencao          THEN 'atencao'
           WHEN u.cota_cm <= r.emergencia_seca  THEN 'emergencia_seca'
           WHEN num_nonnulls(r.atencao, r.alerta, r.inundacao,
                             r.inundacao_severa, r.emergencia_seca) = 0 THEN 'sem_referencia'
           ELSE 'normal'
       END AS situacao
FROM analise.ultima_leitura u
LEFT JOIN ref r ON r.estacao = u.codigo_ana;

CREATE OR REPLACE VIEW analise.comparativo_anual AS
SELECT estacao,
       extract(year FROM dia)::int AS ano,
       to_char(dia, 'MM-DD')       AS mes_dia,
       cota_cm
FROM analise.leituras_diarias;

-- Collection log for the dashboard (last 30 days; raw errors included)
CREATE OR REPLACE VIEW analise.coletas_recentes AS
SELECT id, fonte, inicio, fim, status, leituras_novas, erro
FROM dados.coletas
WHERE inicio >= now() - interval '30 days';

-- Reading quality per station and month (suspicious readings are kept, only counted)
CREATE OR REPLACE VIEW analise.qualidade_mensal AS
SELECT estacao,
       date_trunc('month', instante AT TIME ZONE 'America/Manaus')::date AS mes,
       fonte,
       count(*) FILTER (WHERE qualidade = 'ok')        AS ok,
       count(*) FILTER (WHERE qualidade = 'corrigida') AS corrigidas,
       count(*) FILTER (WHERE qualidade = 'suspeita')  AS suspeitas
FROM dados.leituras
GROUP BY 1, 2, 3;
