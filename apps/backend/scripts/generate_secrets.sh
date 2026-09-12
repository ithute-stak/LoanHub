#!/usr/bin/env bash
set -euo pipefail

PROJECT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
SECRETS_DIR="$PROJECT_ROOT/secrets"
ENV_FILE="$PROJECT_ROOT/.env"
ROTATE=false

if [[ "${1:-}" == "--rotate" ]]; then
    ROTATE=true
elif [[ $# -gt 0 ]]; then
    echo "Usage: $0 [--rotate]" >&2
    exit 1
fi

mkdir -p "$SECRETS_DIR"
chmod 700 "$SECRETS_DIR"
umask 077

if [[ -f "$SECRETS_DIR/jwt_private.pem" || -f "$SECRETS_DIR/jwt_public.pem" ]]; then
    if [[ "$ROTATE" == true ]]; then
        TIMESTAMP="$(date -u +%Y%m%dT%H%M%SZ)"
        BACKUP_DIR="$SECRETS_DIR/rotated-$TIMESTAMP"
        mkdir -p "$BACKUP_DIR"

        [[ -f "$SECRETS_DIR/jwt_private.pem" ]] \
            && mv "$SECRETS_DIR/jwt_private.pem" "$BACKUP_DIR/"

        [[ -f "$SECRETS_DIR/jwt_public.pem" ]] \
            && mv "$SECRETS_DIR/jwt_public.pem" "$BACKUP_DIR/"

        chmod 700 "$BACKUP_DIR"
        echo "Moved previous JWT keys to $BACKUP_DIR"
    else
        echo "JWT keys already exist. Use --rotate to replace exposed or old keys."
    fi
fi

if [[ ! -f "$SECRETS_DIR/jwt_private.pem" || ! -f "$SECRETS_DIR/jwt_public.pem" ]]; then
    openssl genpkey \
        -algorithm RSA \
        -pkeyopt rsa_keygen_bits:3072 \
        -out "$SECRETS_DIR/jwt_private.pem"

    openssl pkey \
        -in "$SECRETS_DIR/jwt_private.pem" \
        -pubout \
        -out "$SECRETS_DIR/jwt_public.pem"

    chmod 600 "$SECRETS_DIR/jwt_private.pem"
    chmod 644 "$SECRETS_DIR/jwt_public.pem"
    echo "Generated fresh JWT key pair."
fi

if [[ ! -f "$ENV_FILE" ]]; then
    cp "$PROJECT_ROOT/.env.example" "$ENV_FILE"
    chmod 600 "$ENV_FILE"
    echo "Created .env from .env.example."
fi

SECRET_VALUE="$(openssl rand -hex 32)"
FERNET_VALUE="$(openssl rand -base64 32 | tr '+/' '-_' | tr -d '\n')"

python3 - "$ENV_FILE" "$SECRET_VALUE" "$FERNET_VALUE" <<'PY'
from pathlib import Path
import sys

path = Path(sys.argv[1])
secret = sys.argv[2]
fernet = sys.argv[3]

lines = path.read_text().splitlines()
values = {
    "SECRET_KEY": secret,
    "FERNET_SECRET_KEY": fernet,
}

result = []
for line in lines:
    key = line.split("=", 1)[0] if "=" in line else None
    if key in values:
        result.append(f"{key}={values[key]}")
    else:
        result.append(line)

path.write_text("\n".join(result) + "\n")
PY

cat <<'MESSAGE'
Security files are ready.

Now edit .env and replace:
  API_DOMAIN
  TLS_EMAIL
  CORS_ORIGINS
  DB_PASSWORD
  any legacy payment-provider values you may still keep outside this cash-only release
MESSAGE
