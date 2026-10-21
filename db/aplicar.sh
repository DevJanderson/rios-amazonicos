#!/usr/bin/env bash
# Aplica db/init/*.sql na instância pg-projects. Idempotente: pode rodar de novo.
# Senhas vêm do .env do projeto e entram pelo stdin do psql (não aparecem na
# linha de comando).
set -euo pipefail

RAIZ="$(cd "$(dirname "$0")/.." && pwd)"
CONTAINER="${PG_CONTAINER:-pg-projects}"

set -a
# shellcheck source=/dev/null
source "$RAIZ/.env"
set +a

: "${RIOS_COLETOR_PASSWORD:?defina no .env}"
: "${RIOS_N8N_PASSWORD:?defina no .env}"
: "${RIOS_LEITURA_PASSWORD:?defina no .env}"

psql_em() {
  docker exec -i -e PGOPTIONS="-c client_min_messages=warning" "$CONTAINER" psql -U postgres -d "$1" -v ON_ERROR_STOP=1 -q
}

{
  printf '\\set pw_coletor %s\n' "$RIOS_COLETOR_PASSWORD"
  printf '\\set pw_n8n %s\n' "$RIOS_N8N_PASSWORD"
  printf '\\set pw_leitura %s\n' "$RIOS_LEITURA_PASSWORD"
  cat "$RAIZ/db/init/00_banco_e_usuarios.sql"
} | psql_em postgres

for arquivo in 01_esquema.sql 02_permissoes.sql 03_carga_inicial.sql 04_bot.sql; do
  psql_em "${RIOS_DB_NAME:-rios}" < "$RAIZ/db/init/$arquivo"
  echo "ok: $arquivo"
done
