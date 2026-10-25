#!/usr/bin/env bash
# Importa credenciais e o workflow do bot no n8n. Idempotente: reimportar atualiza.
# Segredos vêm do .env do projeto e entram pelo stdin do container (não ficam
# em arquivo nem aparecem na linha de comando).
# O workflow entra desativado; ative-o no editor (http://nauraki:5678).
# Sem TELEGRAM_BOT_TOKEN no .env, só a credencial do Postgres é criada; rode de
# novo depois de criar o bot para cadastrar a do Telegram.
set -euo pipefail

RAIZ="$(cd "$(dirname "$0")/.." && pwd)"
CONTAINER="${N8N_CONTAINER:-n8n-app}"

set -a
# shellcheck source=/dev/null
source "$RAIZ/.env"
set +a

: "${RIOS_N8N_PASSWORD:?defina no .env}"

if ! docker inspect "$CONTAINER" --format '{{json .NetworkSettings.Networks}}' | grep -q pg-projects-net; then
  echo "erro: $CONTAINER não está na rede pg-projects-net" >&2
  exit 1
fi

jq -n \
  --arg pw "$RIOS_N8N_PASSWORD" \
  --arg db "${RIOS_DB_NAME:-rios}" \
  --arg token "${TELEGRAM_BOT_TOKEN:-}" \
  '[
    {id: "riosPgN8nCred001", name: "Rios — Postgres (rios_n8n)", type: "postgres",
     data: {host: "pg-projects", port: 5432, database: $db, user: "rios_n8n",
            password: $pw, ssl: "disable", allowUnauthorizedCerts: false}}]
   + if $token == "" then [] else
     [{id: "H0o6aGWwZLH9sCjF", name: "Telegram", type: "telegramApi",
       data: {accessToken: $token, baseUrl: "https://api.telegram.org"}}] end' |
  docker exec -i "$CONTAINER" sh -c \
    'umask 077; f=$(mktemp); cat > "$f"; n8n import:credentials --input="$f"; s=$?; rm -f "$f"; exit $s'
if [ -n "${TELEGRAM_BOT_TOKEN:-}" ]; then
  echo "ok: credenciais (Postgres e Telegram)"
else
  echo "ok: credencial do Postgres (TELEGRAM_BOT_TOKEN ausente: Telegram fica para depois)"
fi

docker exec -i "$CONTAINER" sh -c \
  'f=$(mktemp); cat > "$f"; n8n import:workflow --input="$f"; s=$?; rm -f "$f"; exit $s' \
  < "$RAIZ/n8n/rios-amazonicos.json"
echo "ok: rios-amazonicos.json"
