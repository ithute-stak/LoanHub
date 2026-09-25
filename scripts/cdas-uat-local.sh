#!/usr/bin/env bash
set -Eeuo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
ENV_FILE="$ROOT_DIR/.env.cdas-uat"
SECRETS_DIR="$ROOT_DIR/secrets"
PROJECT_NAME="loanhub-cdas-uat"

compose() {
  docker compose \
    --env-file "$ENV_FILE" \
    -p "$PROJECT_NAME" \
    "$@"
}

require_repo() {
  if [[ ! -f "$ROOT_DIR/compose.yaml" || ! -d "$ROOT_DIR/apps/backend" ]]; then
    echo "Run this script from the LoanHub repository checkout." >&2
    exit 1
  fi
}

require_command() {
  local command_name="$1"
  if ! command -v "$command_name" >/dev/null 2>&1; then
    echo "Missing required command: $command_name" >&2
    exit 1
  fi
}

require_docker() {
  require_command docker
  if ! docker compose version >/dev/null 2>&1; then
    echo "Docker Compose v2 is required (docker compose)." >&2
    exit 1
  fi
  if ! docker info >/dev/null 2>&1; then
    echo "Docker is installed but the Docker daemon is not available." >&2
    exit 1
  fi
}

require_uat_env() {
  if [[ ! -f "$ENV_FILE" ]]; then
    echo "Missing $ENV_FILE. Run: bash scripts/cdas-uat-local.sh init" >&2
    exit 1
  fi

  if ! grep -Fxq 'ENVIRONMENT=development' "$ENV_FILE"; then
    echo "Refusing to run: CDAS UAT environment must use ENVIRONMENT=development." >&2
    exit 1
  fi

  if ! grep -Fxq 'DB_NAME=loanhub_cdas_uat' "$ENV_FILE"; then
    echo "Refusing to run: CDAS UAT must use the isolated loanhub_cdas_uat database." >&2
    exit 1
  fi

  if ! grep -Fxq 'NEXT_PUBLIC_API_URL=http://localhost:18000/api/v1' "$ENV_FILE"; then
    echo "Refusing to run: frontend must point to the local UAT backend." >&2
    exit 1
  fi
}

init_uat() {
  require_repo
  require_command openssl

  if [[ -f "$ENV_FILE" ]]; then
    echo "$ENV_FILE already exists; leaving it unchanged."
  else
    local db_password secret_key fernet_key chat_key file_key
    db_password="$(openssl rand -hex 24)"
    secret_key="$(openssl rand -hex 32)"
    fernet_key="$(openssl rand -base64 32 | tr '+/' '-_' | tr -d '\n')"
    chat_key="$(openssl rand -hex 32)"
    file_key="$(openssl rand -hex 32)"

    umask 077
    cat > "$ENV_FILE" <<EOF
COMPOSE_PROJECT_NAME=$PROJECT_NAME
LOANHUB_BACKEND_IMAGE=loanhub-cdas-uat-backend
LOANHUB_FRONTEND_IMAGE=loanhub-cdas-uat-frontend
LOANHUB_IMAGE_TAG=local
LOANHUB_ENV_FILE=.env.cdas-uat

ENVIRONMENT=development
APP_TIMEZONE=Africa/Maseru
PUBLIC_APP_URL=http://localhost:13000
CORS_ORIGINS=http://localhost:13000
NEXT_PUBLIC_API_URL=http://localhost:18000/api/v1

BACKEND_BIND=127.0.0.1
BACKEND_PORT=18000
FRONTEND_BIND=127.0.0.1
FRONTEND_PORT=13000

DB_NAME=loanhub_cdas_uat
DB_USER=loanhub_uat
DB_PASSWORD=$db_password

SECRET_KEY=$secret_key
FERNET_SECRET_KEY=$fernet_key
CHAT_ENCRYPTION_KEY=$chat_key
FILE_ENCRYPTION_KEY=$file_key

CDAS_TIMEOUT_SECONDS=20
SANDBOX_MODE=true
SANDBOX_ROLE_SWITCH_ENABLED=true
SANDBOX_LOGIN_PHONE=12345678
SANDBOX_LOGIN_PASSWORD=1234567890

RATE_LIMIT_ENABLED=false
METRICS_ENABLED=false
MIDNIGHT_REPORTS_ENABLED=false
COLLECTION_DAILY_REPORT_ENABLED=false
TREASURY_AUTO_SUBMIT_ENABLED=false
CALL_MEDIA_PROVIDER=disabled
MALWARE_SCAN_ENABLED=false
EOF
    chmod 600 "$ENV_FILE"
    echo "Created isolated local UAT environment: $ENV_FILE"
  fi

  mkdir -p "$SECRETS_DIR"
  chmod 700 "$SECRETS_DIR"

  if [[ ! -f "$SECRETS_DIR/jwt_private.pem" || ! -f "$SECRETS_DIR/jwt_public.pem" ]]; then
    umask 077
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
    echo "Generated local JWT key pair."
  else
    echo "Existing JWT keys found; leaving them unchanged."
  fi

  require_uat_env
  echo "CDAS UAT local environment is ready. CDAS provider credentials are NOT stored by this script."
}

up_uat() {
  require_uat_env
  require_docker
  cd "$ROOT_DIR"
  compose up -d --build db redis migrate backend frontend
  echo
  compose ps
  echo
  echo "LoanHub frontend: http://localhost:13000"
  echo "LoanHub API:      http://localhost:18000/api/v1"
  echo "Maintenance worker was intentionally NOT started."
}

wait_for_backend() {
  require_command curl
  local attempt
  echo "Waiting for LoanHub backend readiness..."
  for attempt in $(seq 1 60); do
    if curl -fsS http://127.0.0.1:18000/health/ready >/dev/null 2>&1; then
      echo "LoanHub backend is ready."
      return 0
    fi
    sleep 2
  done

  echo "Backend did not become ready within 120 seconds." >&2
  compose logs --tail=100 backend migrate >&2 || true
  exit 1
}

seed_uat() {
  require_uat_env
  require_docker
  cd "$ROOT_DIR"
  compose exec -u app backend python scripts/seed_sandbox.py
}

status_uat() {
  require_uat_env
  require_docker
  require_command curl
  cd "$ROOT_DIR"
  compose ps
  echo
  curl -fsS http://127.0.0.1:18000/health/ready
  echo
}

start_uat() {
  require_repo
  require_command openssl
  require_command curl
  require_docker
  init_uat
  up_uat
  wait_for_backend
  seed_uat
  status_uat
  echo
  echo "CDAS UAT is ready at http://localhost:13000"
  echo "Configure authorised CDAS TEST credentials through Company Settings before provider testing."
}

logs_uat() {
  require_uat_env
  require_docker
  cd "$ROOT_DIR"
  compose logs --tail=200 backend frontend migrate
}

down_uat() {
  require_uat_env
  require_docker
  cd "$ROOT_DIR"
  compose down
  echo "Stopped the isolated CDAS UAT stack. Volumes were preserved."
}

usage() {
  cat <<'EOF'
Usage: bash scripts/cdas-uat-local.sh <command>

Commands:
  start   Preflight, initialize, start, wait, seed and verify the local UAT stack
  init    Create isolated local UAT env and JWT keys without CDAS credentials
  up      Build/start db, redis, migrate, backend and frontend only
  seed    Seed the isolated LoanHub sandbox company/user/client fixtures
  status  Show containers and backend readiness
  logs    Show recent backend/frontend/migration logs
  down    Stop UAT containers while preserving UAT volumes

This helper never starts the maintenance service and never stores CDAS provider
credentials. Configure authorised CDAS TEST credentials through LoanHub Company
Settings after the local application is running.
EOF
}

case "${1:-}" in
  start) start_uat ;;
  init) init_uat ;;
  up) up_uat ;;
  seed) seed_uat ;;
  status) status_uat ;;
  logs) logs_uat ;;
  down) down_uat ;;
  *) usage; exit 2 ;;
esac
