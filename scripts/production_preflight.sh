#!/usr/bin/env bash
set -Eeuo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT_DIR"

ENV_FILE="${LOANHUB_PRODUCTION_ENV_FILE:-.env.production}"

if [[ ! -f "$ENV_FILE" ]]; then
    echo "[LoanHub] Missing $ENV_FILE. Run: bash ./scripts/prepare_production_env.sh <email>"
    exit 1
fi

set -a
# shellcheck disable=SC1090
source "$ENV_FILE"
set +a

required=(
    APP_DOMAIN
    API_DOMAIN
    WWW_DOMAIN
    TLS_EMAIL
    PUBLIC_APP_URL
    CORS_ORIGINS
    NEXT_PUBLIC_API_URL
    DB_NAME
    DB_USER
    DB_PASSWORD
    SECRET_KEY
    FERNET_SECRET_KEY
    CHAT_ENCRYPTION_KEY
    FILE_ENCRYPTION_KEY
    BOOTSTRAP_SUPERADMIN_PASSWORD
)

for key in "${required[@]}"; do
    value="${!key:-}"
    if [[ -z "$value" ]]; then
        echo "[LoanHub] Missing required production setting: $key"
        exit 1
    fi
    if [[ "$value" == *"replace-with"* || "$value" == *"example.com"* ]]; then
        echo "[LoanHub] Placeholder value still present for: $key"
        exit 1
    fi
done

if [[ ${#BOOTSTRAP_SUPERADMIN_PASSWORD} -lt 12 ]]; then
    echo "[LoanHub] BOOTSTRAP_SUPERADMIN_PASSWORD must contain at least 12 characters."
    exit 1
fi

if [[ "$APP_DOMAIN" != "loanhub.co.ls" ]]; then
    echo "[LoanHub] APP_DOMAIN must be loanhub.co.ls (found: $APP_DOMAIN)"
    exit 1
fi

if [[ "$API_DOMAIN" != "api.loanhub.co.ls" ]]; then
    echo "[LoanHub] API_DOMAIN must be api.loanhub.co.ls (found: $API_DOMAIN)"
    exit 1
fi

if [[ "$PUBLIC_APP_URL" != "https://${APP_DOMAIN}" ]]; then
    echo "[LoanHub] PUBLIC_APP_URL must be https://${APP_DOMAIN}"
    exit 1
fi

if [[ "$NEXT_PUBLIC_API_URL" != "https://${API_DOMAIN}/api/v1" ]]; then
    echo "[LoanHub] NEXT_PUBLIC_API_URL must be https://${API_DOMAIN}/api/v1"
    exit 1
fi

if [[ "$CORS_ORIGINS" != *"https://${APP_DOMAIN}"* ]]; then
    echo "[LoanHub] CORS_ORIGINS must include https://${APP_DOMAIN}"
    exit 1
fi

for key_file in secrets/jwt_private.pem secrets/jwt_public.pem; do
    if [[ ! -s "$key_file" ]]; then
        echo "[LoanHub] Missing JWT key: $key_file"
        exit 1
    fi
done

command -v docker >/dev/null || {
    echo "[LoanHub] Docker is not installed."
    exit 1
}

docker compose version >/dev/null
LOANHUB_ENV_FILE="$ENV_FILE" docker compose --env-file "$ENV_FILE" --profile production config >/dev/null

echo "[LoanHub] Production preflight passed using $ENV_FILE."
