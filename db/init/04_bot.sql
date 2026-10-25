-- Telegram bot logic (Fase 5). Roda no banco "rios". Idempotente.
--
-- O n8n só repassa mensagens: toda a regra fica aqui, testável com pytest.
--   bot.responder(chat_id, texto) -> resposta de qualquer comando
--   bot.boletim()                 -> boletim diário dos 4 rios
--   bot.alertas_pendentes()       -> alertas a enviar (situação mudou)
--   bot.marcar_alerta(...)        -> registra o alerta enviado (não repete)
-- Mensagens em texto puro (sem parse_mode), para não precisar escapar nada.

CREATE SCHEMA IF NOT EXISTS bot;

-- Readings older than this are reported as "sem dados recentes"
CREATE OR REPLACE FUNCTION bot.limite_dados_recentes() RETURNS interval
LANGUAGE sql IMMUTABLE AS $$ SELECT interval '3 days' $$;

CREATE OR REPLACE FUNCTION bot.normalizar(texto text) RETURNS text
LANGUAGE sql IMMUTABLE AS $$
    SELECT regexp_replace(
        translate(lower(trim(coalesce(texto, ''))), 'áàâãäéèêëíìîïóòôõöúùûüç', 'aaaaaeeeeiiiiooooouuuuc'),
        '\s+', ' ', 'g')
$$;

CREATE OR REPLACE FUNCTION bot.metros(cota_cm numeric) RETURNS text
LANGUAGE sql IMMUTABLE AS $$
    SELECT replace(to_char(cota_cm / 100.0, 'FM990.00'), '.', ',') || ' m'
$$;

CREATE OR REPLACE FUNCTION bot.variacao(cm numeric) RETURNS text
LANGUAGE sql IMMUTABLE AS $$
    SELECT CASE
        WHEN cm IS NULL THEN 'sem dado de 24 h atrás'
        WHEN cm > 0 THEN '▲ subiu ' || abs(round(cm)) || ' cm em 24 h'
        WHEN cm < 0 THEN '▼ desceu ' || abs(round(cm)) || ' cm em 24 h'
        ELSE '= estável em 24 h'
    END
$$;

CREATE OR REPLACE FUNCTION bot.rotulo_situacao(situacao text) RETURNS text
LANGUAGE sql IMMUTABLE AS $$
    SELECT CASE situacao
        WHEN 'inundacao_severa' THEN '🟣 Inundação severa'
        WHEN 'inundacao'        THEN '🔴 Inundação'
        WHEN 'alerta'           THEN '🟠 Alerta'
        WHEN 'atencao'          THEN '🟡 Atenção'
        WHEN 'emergencia_seca'  THEN '🟤 Emergência de seca'
        WHEN 'normal'           THEN '🟢 Normal'
        WHEN 'sem_referencia'   THEN '⚪ Sem cotas de referência'
        ELSE '⚪ ' || coalesce(situacao, 'desconhecida')
    END
$$;

-- Station code from free text ("manaus", "Sao Gabriel", "14990000")
CREATE OR REPLACE FUNCTION bot.buscar_estacao(texto text) RETURNS text
LANGUAGE sql STABLE AS $$
    SELECT e.codigo_ana
    FROM analise.estacoes e
    WHERE bot.normalizar(texto) <> ''
      AND (e.codigo_ana = trim(texto)
           OR bot.normalizar(e.nome) LIKE bot.normalizar(texto) || '%'
           OR bot.normalizar(e.municipio) LIKE bot.normalizar(texto) || '%')
    ORDER BY bot.normalizar(e.nome) = bot.normalizar(texto) DESC, e.rio, e.ordem_no_rio
    LIMIT 1
$$;

CREATE OR REPLACE FUNCTION bot.lista_estacoes() RETURNS text
LANGUAGE sql STABLE AS $$
    SELECT string_agg(rio || ': ' || nomes, E'\n' ORDER BY ordem)
    FROM (
        SELECT rio, min(rio_id) AS ordem, string_agg(nome, ', ' ORDER BY ordem_no_rio) AS nomes
        FROM analise.estacoes
        GROUP BY rio
    ) r
$$;

CREATE OR REPLACE FUNCTION bot.ajuda() RETURNS text
LANGUAGE sql STABLE AS $$
    SELECT 'Comandos:' || E'\n'
        || '/nivel <cidade> — cota atual, variação e situação' || E'\n'
        || '/semana <cidade> — últimos 7 dias' || E'\n'
        || '/alertas — escolher estações para receber alertas' || E'\n'
        || '/parar — deixar de receber mensagens' || E'\n\n'
        || 'Estações (da nascente para a foz):' || E'\n' || bot.lista_estacoes() || E'\n\n'
        || 'Fonte: ANA (telemetria) e SGB (cotas de referência). '
        || 'Não substitui os alertas oficiais da Defesa Civil.'
$$;

CREATE OR REPLACE FUNCTION bot.nivel(codigo text) RETURNS text
LANGUAGE sql STABLE AS $$
    SELECT s.nome || ' (rio ' || s.rio || ')' || E'\n'
        || CASE WHEN s.instante < now() - bot.limite_dados_recentes()
                THEN '⚠️ Sem dados recentes. Última leitura: ' ELSE '' END
        || bot.metros(s.cota_cm) || ' em '
        || to_char(s.instante AT TIME ZONE 'America/Manaus', 'DD/MM/YYYY HH24:MI') || ' (hora de Manaus)' || E'\n'
        || bot.variacao(s.variacao_24h_cm) || E'\n'
        || bot.rotulo_situacao(s.situacao)
        || coalesce(E'\n' || 'Há um ano: ' || bot.metros(a.cota_cm)
                    || ' (' || CASE WHEN s.cota_cm >= a.cota_cm THEN '+' ELSE '−' END
                    || bot.metros(abs(s.cota_cm - a.cota_cm)) || ')', '')
    FROM analise.situacao_estacao s
    LEFT JOIN analise.leituras_diarias a
           ON a.estacao = s.codigo_ana
          AND a.dia = (s.instante AT TIME ZONE 'America/Manaus')::date - interval '1 year'
    WHERE s.codigo_ana = codigo
$$;

CREATE OR REPLACE FUNCTION bot.semana(codigo text) RETURNS text
LANGUAGE sql STABLE AS $$
    SELECT e.nome || ' — últimos 7 dias' || E'\n'
        || coalesce(
            (SELECT string_agg(to_char(d.dia, 'DD/MM') || '  ' || bot.metros(d.cota_cm)
                                || coalesce('  (' || CASE WHEN d.cota_cm - d.anterior >= 0 THEN '+' ELSE '' END
                                            || round(d.cota_cm - d.anterior) || ' cm)', ''),
                               E'\n' ORDER BY d.dia)
             FROM (SELECT dia, cota_cm, lag(cota_cm) OVER (ORDER BY dia) AS anterior
                   FROM analise.leituras_diarias
                   WHERE estacao = codigo
                     AND dia >= (now() AT TIME ZONE 'America/Manaus')::date - 7) d
             WHERE d.dia >= (now() AT TIME ZONE 'America/Manaus')::date - 6),
            '⚠️ Sem leituras nos últimos 7 dias.')
    FROM analise.estacoes e
    WHERE e.codigo_ana = codigo
$$;

CREATE OR REPLACE FUNCTION bot.boletim() RETURNS text
LANGUAGE sql STABLE AS $$
    SELECT '🌊 Boletim dos rios — '
        || to_char(now() AT TIME ZONE 'America/Manaus', 'DD/MM/YYYY') || E'\n'
        || string_agg(linha, E'\n' ORDER BY rio_id, ordem_no_rio) || E'\n\n'
        || '▲ subindo  ▼ descendo (24 h). Fonte: ANA/SGB.' || E'\n'
        || 'Detalhes: /nivel <cidade>'
    FROM (
        SELECT e.rio_id, e.ordem_no_rio,
               CASE WHEN e.ordem_no_rio = 1 THEN E'\n' || 'Rio ' || e.rio || E'\n' ELSE '' END
               || '• ' || e.nome || ': '
               || CASE
                      WHEN s.instante IS NULL OR s.instante < now() - bot.limite_dados_recentes()
                          THEN 'sem dados recentes'
                      ELSE bot.metros(s.cota_cm)
                           || CASE WHEN s.variacao_24h_cm > 0 THEN ' ▲' || round(s.variacao_24h_cm) || ' cm'
                                   WHEN s.variacao_24h_cm < 0 THEN ' ▼' || round(abs(s.variacao_24h_cm)) || ' cm'
                                   ELSE '' END
                           || CASE WHEN s.situacao NOT IN ('normal', 'sem_referencia')
                                   THEN '  ' || bot.rotulo_situacao(s.situacao) ELSE '' END
                  END AS linha
        FROM analise.estacoes e
        LEFT JOIN analise.situacao_estacao s ON s.codigo_ana = e.codigo_ana
    ) l
$$;

CREATE OR REPLACE FUNCTION bot.definir_alertas(chat bigint, argumento text) RETURNS text
LANGUAGE plpgsql AS $$
DECLARE
    escolhidas text[] := '{}';
    nao_achadas text[] := '{}';
    parte text;
    codigo text;
    atuais text[];
BEGIN
    IF bot.normalizar(argumento) = '' THEN
        SELECT estacoes INTO atuais FROM dados.inscritos WHERE chat_id = chat;
        RETURN 'Você recebe alertas de: '
            || coalesce((SELECT string_agg(e.nome, ', ' ORDER BY e.rio_id, e.ordem_no_rio)
                         FROM analise.estacoes e WHERE e.codigo_ana = ANY (atuais)), 'nenhuma estação')
            || E'\n\n' || 'Para escolher: /alertas manaus, humaitá' || E'\n'
            || 'Para todas: /alertas todas   Para nenhuma: /alertas nenhuma';
    END IF;

    IF bot.normalizar(argumento) = 'todas' THEN
        SELECT array_agg(codigo_ana) INTO escolhidas FROM analise.estacoes;
    ELSIF bot.normalizar(argumento) NOT IN ('nenhuma', 'nenhum') THEN
        FOREACH parte IN ARRAY regexp_split_to_array(argumento, '\s*[,;]\s*') LOOP
            CONTINUE WHEN bot.normalizar(parte) = '';
            codigo := bot.buscar_estacao(parte);
            IF codigo IS NULL THEN
                nao_achadas := nao_achadas || trim(parte);
            ELSIF NOT codigo = ANY (escolhidas) THEN
                escolhidas := escolhidas || codigo;
            END IF;
        END LOOP;
        IF cardinality(nao_achadas) > 0 THEN
            RETURN 'Não encontrei: ' || array_to_string(nao_achadas, ', ') || E'\n\n'
                || 'Estações:' || E'\n' || bot.lista_estacoes();
        END IF;
    END IF;

    -- Baseline = current situation, so choosing a station never fires an old alert
    INSERT INTO dados.inscritos AS i (chat_id, estacoes, ultimos_alertas)
    VALUES (chat, escolhidas,
            coalesce((SELECT jsonb_object_agg(codigo_ana, situacao) FROM analise.situacao_estacao
                      WHERE codigo_ana = ANY (escolhidas)), '{}'))
    ON CONFLICT (chat_id) DO UPDATE SET
        estacoes = EXCLUDED.estacoes,
        ativo = true,
        ultimos_alertas = EXCLUDED.ultimos_alertas || (i.ultimos_alertas - EXCLUDED.estacoes)
            - (SELECT coalesce(array_agg(k), '{}') FROM jsonb_object_keys(i.ultimos_alertas) k
               WHERE NOT k = ANY (EXCLUDED.estacoes));

    IF cardinality(escolhidas) = 0 THEN
        RETURN 'Pronto: você não recebe mais alertas de estação. O boletim diário continua.';
    END IF;
    RETURN '✅ Alertas ativos para: '
        || (SELECT string_agg(e.nome, ', ' ORDER BY e.rio_id, e.ordem_no_rio)
            FROM analise.estacoes e WHERE e.codigo_ana = ANY (escolhidas))
        || E'\n' || 'Você recebe uma mensagem quando a situação de uma delas mudar.';
END
$$;

-- Single entry point for every Telegram message
CREATE OR REPLACE FUNCTION bot.responder(chat bigint, mensagem text) RETURNS text
LANGUAGE plpgsql AS $$
DECLARE
    comando text := lower(split_part(split_part(trim(coalesce(mensagem, '')), ' ', 1), '@', 1));
    argumento text := trim(substr(trim(coalesce(mensagem, '')), length(split_part(trim(coalesce(mensagem, '')), ' ', 1)) + 1));
    codigo text;
BEGIN
    IF comando = '/start' THEN
        INSERT INTO dados.inscritos (chat_id) VALUES (chat)
        ON CONFLICT (chat_id) DO UPDATE SET ativo = true;
        RETURN '🌊 Olá! Este bot acompanha o nível dos rios Negro, Solimões, Madeira e Amazonas.'
            || E'\n' || 'Você vai receber um boletim por dia. Para alertas de uma estação, use /alertas.'
            || E'\n\n' || bot.ajuda();
    ELSIF comando = '/parar' THEN
        UPDATE dados.inscritos SET ativo = false WHERE chat_id = chat;
        RETURN 'Inscrição cancelada. Você não recebe mais boletins nem alertas. Para voltar: /start';
    ELSIF comando = '/alertas' THEN
        RETURN bot.definir_alertas(chat, argumento);
    ELSIF comando IN ('/nivel', '/semana') THEN
        IF argumento = '' THEN
            RETURN 'Diga a cidade. Exemplo: ' || comando || ' manaus' || E'\n\n'
                || 'Estações:' || E'\n' || bot.lista_estacoes();
        END IF;
        codigo := bot.buscar_estacao(argumento);
        IF codigo IS NULL THEN
            RETURN 'Não encontrei "' || argumento || '".' || E'\n\n' || 'Estações:' || E'\n' || bot.lista_estacoes();
        END IF;
        RETURN coalesce(CASE comando WHEN '/nivel' THEN bot.nivel(codigo) ELSE bot.semana(codigo) END,
                        '⚠️ Ainda não há leituras para essa estação.');
    ELSIF comando = '/boletim' THEN
        RETURN bot.boletim();
    END IF;
    RETURN bot.ajuda();
END
$$;

-- One row per (subscriber, station) whose situation changed since the last alert
CREATE OR REPLACE FUNCTION bot.alertas_pendentes()
RETURNS TABLE (chat_id bigint, estacao text, situacao text, mensagem text)
LANGUAGE sql STABLE AS $$
    SELECT i.chat_id, s.codigo_ana, s.situacao,
           '🔔 ' || s.nome || ': ' || bot.rotulo_situacao(s.situacao) || E'\n'
           || 'Antes: ' || bot.rotulo_situacao(i.ultimos_alertas ->> s.codigo_ana) || E'\n'
           || 'Agora: ' || bot.metros(s.cota_cm) || ', ' || bot.variacao(s.variacao_24h_cm) || E'\n'
           || 'Fonte: ANA/SGB. Siga as orientações da Defesa Civil.'
    FROM dados.inscritos i
    JOIN analise.situacao_estacao s ON s.codigo_ana = ANY (i.estacoes)
    WHERE i.ativo
      AND s.situacao <> 'sem_referencia'
      AND s.instante >= now() - bot.limite_dados_recentes()
      AND s.situacao IS DISTINCT FROM i.ultimos_alertas ->> s.codigo_ana
$$;

CREATE OR REPLACE FUNCTION bot.marcar_alerta(chat bigint, codigo text, nova_situacao text) RETURNS void
LANGUAGE sql AS $$
    UPDATE dados.inscritos
    SET ultimos_alertas = ultimos_alertas || jsonb_build_object(codigo, nova_situacao)
    WHERE chat_id = chat
$$;

CREATE OR REPLACE FUNCTION bot.inscritos_ativos() RETURNS SETOF bigint
LANGUAGE sql STABLE AS $$ SELECT chat_id FROM dados.inscritos WHERE ativo ORDER BY chat_id $$;

-- Telegram answers 403 when the user blocked the bot or deleted the chat:
-- stop sending to that chat (it comes back with /start)
CREATE OR REPLACE FUNCTION bot.desativar_se_bloqueado(chat bigint, erro text) RETURNS boolean
LANGUAGE sql AS $$
    UPDATE dados.inscritos SET ativo = false
    WHERE chat_id = chat
      AND (erro ILIKE '%403%' OR erro ILIKE '%blocked%' OR erro ILIKE '%chat not found%'
           OR erro ILIKE '%deactivated%')
    RETURNING true
$$;

-- Only rios_n8n runs the bot
REVOKE ALL ON SCHEMA bot FROM PUBLIC;
REVOKE EXECUTE ON ALL FUNCTIONS IN SCHEMA bot FROM PUBLIC;
GRANT USAGE ON SCHEMA bot TO rios_n8n;
GRANT EXECUTE ON ALL FUNCTIONS IN SCHEMA bot TO rios_n8n;
