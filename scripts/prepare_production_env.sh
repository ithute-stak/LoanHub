#!/usr/bin/env bash
set -Eeuo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT_DIR"

TEMPLATE=".env.production.example"
ENV_FILE="${LOANHUB_PRODUCTION_ENV_FILE:-.env.production}"
TLS_EMAIL="${1:-}"

if [[ ! -f "$TEMPLATE" ]]; then
    echo "[LoanHub] Missing $TEMPLATE"
    exit 1
fi

if [[ -e "$ENV_FILE" ]]; then
    echo "[LoanHub] $ENV_FILE already exists; refusing to overwrite production configuration."
    echo "[LoanHub] Your normal development .env is left untouched."
    echo "[LoanHub] Edit $ENV_FILE or move it aside before running this helper again."
    exit 1
fi

if [[ -z "$TLS_EMAIL" ]]; then
    read -r -p "TLS/Let's Encrypt email: " TLS_EMAIL
fi

if [[ -z "$TLS_EMAIL" || "$TLS_EMAIL" != *@*.* ]]; then
    echo "[LoanHub] A valid email address is required for TLS certificate notices."
    exit 1
fi

command -v python3 >/dev/null || {
    echo "[LoanHub] python3 is required."
    exit 1
}
command -v openssl >/dev/null || {
    echo "[LoanHub] openssl is required."
    exit 1
}

cp "$TEMPLATE" "$ENV_FILE"

set_env() {
    local key="$1"
    local value="$2"
    python3 - "$ENV_FILE" "$key" "$value" <<'PY'
from pathlib import Path
import sys

path = Path(sys.argv[1])
key = sys.argv[2]
value = sys.argv[3]
lines = path.read_text().splitlines()
prefix = f"{key}="
replaced = False
for index, line in enumerate(lines):
    if line.startswith(prefix):
        lines[index] = f"{key}={value}"
        replaced = True
        break
if not replaced:
    lines.append(f"{key}={value}")
path.write_text("\n".join(lines) + "\n")
PY
}

random_hex() {
    openssl rand -hex 32
}

fernet_key() {
    python3 - <<'PY'
import base64
import os
print(base64.urlsafe_b64encode(os.urandom(32)).decode())
PY
}

set_env LOANHUB_ENV_FILE "$ENV_FILE"
set_env TLS_EMAIL "$TLS_EMAIL"
set_env DB_PASSWORD "$(random_hex)"
set_env SECRET_KEY "$(random_hex)"
set_env FERNET_SECRET_KEY "$(fernet_key)"
set_env CHAT_ENCRYPTION_KEY "$(random_hex)"
set_env FILE_ENCRYPTION_KEY "$(random_hex)"
set_env MINIO_ROOT_PASSWORD "$(random_hex)"

mkdir -p secrets
BOOTSTRAP_PASSWORD="$(random_hex)"
set_env BOOTSTRAP_SUPERADMIN_ENABLED "true"
set_env BOOTSTRAP_SUPERADMIN_PASSWORD "$BOOTSTRAP_PASSWORD"
umask 077
printf '%s\n' "$BOOTSTRAP_PASSWORD" > secrets/initial_superadmin_password.txt
unset BOOTSTRAP_PASSWORD

if [[ ! -f secrets/jwt_private.pem || ! -f secrets/jwt_public.pem ]]; then
    echo "[LoanHub] Generating production JWT key pair"
    openssl genpkey \
        -algorithm RSA \
        -pkeyopt rsa_keygen_bits:3072 \
        -out secrets/jwt_private.pem >/dev/null 2>&1
    openssl pkey \
        -in secrets/jwt_private.pem \
        -pubout \
        -out secrets/jwt_public.pem >/dev/null 2>&1
fi

chmod 600 "$ENV_FILE" secrets/jwt_private.pem secrets/initial_superadmin_password.txt
chmod 644 secrets/jwt_public.pem

echo "[LoanHub] Production configuration prepared in $ENV_FILE."
echo "[LoanHub] Your development .env was not changed."
echo "[LoanHub] Initial super-admin password saved in secrets/initial_superadmin_password.txt."
echo "[LoanHub] Delete that one-time credential file after the first successful login and password change."
echo "[LoanHub] Frontend: https://loanhub.co.ls"
echo "[LoanHub] API:      https://api.loanhub.co.ls"
echo
echo "[LoanHub] Before deployment:"
echo "  1. Point DNS A records for @, api and www to the VPS."
echo "  2. Allow inbound TCP 22, 80 and 443 (and UDP 443 if desired for HTTP/3)."
echo "  3. Review $ENV_FILE, then run: ./scripts/deploy_hostinger.sh"
