#!/usr/bin/env sh
set -eu

ROOT_DIR=$(CDPATH= cd -- "$(dirname -- "$0")/.." && pwd)
cd "$ROOT_DIR"

command -v openssl >/dev/null 2>&1 || {
    echo "openssl is required." >&2
    exit 1
}
command -v python3 >/dev/null 2>&1 || {
    echo "python3 is required." >&2
    exit 1
}

umask 077
mkdir -p secrets

if [ ! -f secrets/jwt_private.pem ]; then
    openssl genpkey -algorithm RSA -pkeyopt rsa_keygen_bits:3072 -out secrets/jwt_private.pem
fi
if [ ! -f secrets/jwt_public.pem ]; then
    openssl pkey -in secrets/jwt_private.pem -pubout -out secrets/jwt_public.pem
fi
chmod 600 secrets/jwt_private.pem
chmod 644 secrets/jwt_public.pem

if [ -f .env ]; then
    echo ".env already exists; it was not overwritten."
else
    python3 <<'PY'
from __future__ import annotations

import base64
import os
import secrets
from pathlib import Path

values = {
    "DB_PASSWORD": secrets.token_urlsafe(36),
    "SECRET_KEY": secrets.token_urlsafe(48),
    "FERNET_SECRET_KEY": base64.urlsafe_b64encode(os.urandom(32)).decode(),
    "CHAT_ENCRYPTION_KEY": base64.urlsafe_b64encode(os.urandom(32)).decode(),
    "FILE_ENCRYPTION_KEY": base64.urlsafe_b64encode(os.urandom(32)).decode(),
}

template = Path(".env.docker.example").read_text(encoding="utf-8")
for key, value in values.items():
    lines = []
    for line in template.splitlines():
        if line.startswith(f"{key}="):
            line = f"{key}={value}"
        lines.append(line)
    template = "\n".join(lines) + "\n"
Path(".env").write_text(template, encoding="utf-8")
PY
    chmod 600 .env
    echo "Created .env with random deployment secrets."
fi

echo "Docker initialization complete."
echo "Review PUBLIC_APP_URL, CORS_ORIGINS and NEXT_PUBLIC_API_URL in .env before deployment."
