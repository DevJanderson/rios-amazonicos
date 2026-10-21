-- Permissões mínimas por usuário. Roda no banco "rios". Idempotente.

-- rios_coletor: grava bruto e dados (exceto inscritos); lê analise para conferência
GRANT USAGE ON SCHEMA bruto, dados, analise TO rios_coletor;
GRANT SELECT, INSERT, DELETE ON bruto.respostas TO rios_coletor;
GRANT SELECT ON dados.rios, dados.estacoes, dados.cotas_referencia TO rios_coletor;
GRANT SELECT, INSERT, UPDATE ON dados.coletas, dados.leituras TO rios_coletor;
GRANT SELECT ON ALL TABLES IN SCHEMA analise TO rios_coletor;

-- rios_n8n: lê analise; mantém inscritos (cadastro e marca de alerta enviado)
GRANT USAGE ON SCHEMA dados, analise TO rios_n8n;
GRANT SELECT ON ALL TABLES IN SCHEMA analise TO rios_n8n;
GRANT SELECT, INSERT, UPDATE ON dados.inscritos TO rios_n8n;

-- rios_leitura: só lê analise (painel, DBeaver, análises)
GRANT USAGE ON SCHEMA analise TO rios_leitura;
GRANT SELECT ON ALL TABLES IN SCHEMA analise TO rios_leitura;
