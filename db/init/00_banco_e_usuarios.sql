-- Banco "rios" e usuários por serviço. Roda no banco "postgres" como superusuário.
-- Idempotente. Senhas chegam como variáveis do psql (ver db/aplicar.sh).
-- Usuários com prefixo "rios_" porque a instância pg-projects é compartilhada.

SELECT format('CREATE ROLE %I LOGIN', r)
FROM unnest(ARRAY['rios_coletor', 'rios_n8n', 'rios_leitura']) AS r
WHERE NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = r)
\gexec

ALTER ROLE rios_coletor WITH LOGIN NOSUPERUSER NOCREATEDB NOCREATEROLE PASSWORD :'pw_coletor';
ALTER ROLE rios_n8n     WITH LOGIN NOSUPERUSER NOCREATEDB NOCREATEROLE PASSWORD :'pw_n8n';
ALTER ROLE rios_leitura WITH LOGIN NOSUPERUSER NOCREATEDB NOCREATEROLE PASSWORD :'pw_leitura';

-- Evita travar o banco com consultas esquecidas
ALTER ROLE rios_n8n     SET statement_timeout = '15s';
ALTER ROLE rios_leitura SET statement_timeout = '60s';

SELECT 'CREATE DATABASE rios'
WHERE NOT EXISTS (SELECT 1 FROM pg_database WHERE datname = 'rios')
\gexec

REVOKE ALL ON DATABASE rios FROM PUBLIC;
GRANT CONNECT ON DATABASE rios TO rios_coletor, rios_n8n, rios_leitura;
