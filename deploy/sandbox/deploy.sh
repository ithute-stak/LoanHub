#!/usr/bin/env bash
set -Eeuo pipefail
umask 077
release="${1:-}"
[[ "$release" =~ ^[0-9a-f]{40}$ && "$#" == 1 ]] || exit 2
cd -- "$(dirname -- "$(realpath -- "${BASH_SOURCE[0]}")")"
[[ "$PWD" == /opt/loanhub/deploy/sandbox ]] || exit 2
unset DOCKER_CONTEXT DOCKER_HOST DOCKER_TLS_VERIFY DOCKER_CERT_PATH COMPOSE_FILE COMPOSE_PROJECT_NAME COMPOSE_PROFILES COMPOSE_ENV_FILES
export DOCKER_HOST=unix:///var/run/docker.sock
exec 9> .reset.lock
flock -n 9
backend="ghcr.io/ithute-stak/loanhub-backend:$release"
frontend="ghcr.io/ithute-stak/loanhub-sandbox-frontend:$release"
docker pull "$backend"
docker pull "$frontend"
mkdir -p secrets
if [[ ! -e sandbox.env ]]; then
  [[ ! -e secrets/jwt_private.pem && ! -e secrets/jwt_public.pem ]] || exit 1
  openssl genpkey -algorithm RSA -pkeyopt rsa_keygen_bits:2048 -out secrets/jwt_private.pem
  openssl pkey -in secrets/jwt_private.pem -pubout -out secrets/jwt_public.pem
  tmp="$(mktemp .sandbox.env.XXXXXX)"
  {
    echo "SANDBOX_DB_PASSWORD=$(openssl rand -hex 32)"
    echo "SANDBOX_RUNTIME_PASSWORD=$(openssl rand -hex 32)"
    echo "SANDBOX_LOGIN_PASSWORD=sandox123"
    echo "SECRET_KEY=$(openssl rand -hex 32)"
    echo "FERNET_SECRET_KEY=$(openssl rand -base64 32 | tr '+/' '-_')"
  } > "$tmp"
  mv "$tmp" sandbox.env
fi
test -s secrets/jwt_private.pem
test -s secrets/jwt_public.pem
chmod 600 sandbox.env secrets/jwt_private.pem
tmp="$(mktemp .sandbox.env.XXXXXX)"
grep -vE '^SANDBOX_(BACKEND|FRONTEND)_IMAGE=' sandbox.env > "$tmp"
printf 'SANDBOX_BACKEND_IMAGE=%s\nSANDBOX_FRONTEND_IMAGE=%s\n' "$backend" "$frontend" >> "$tmp"
mv "$tmp" sandbox.env
compose=(docker compose --project-name loanhub-sandbox --project-directory "$PWD" --env-file "$PWD/sandbox.env" -f "$PWD/compose.yaml" --profile verified)
"${compose[@]}" config --format json | python3 -c '
import json,sys
c=json.load(sys.stdin)
assert c["name"]=="loanhub-sandbox"
assert set(c["networks"])=={"isolated"}
assert c["networks"]["isolated"]["internal"] is True
assert set(c["volumes"])=={"sandbox_db","sandbox_redis","sandbox_files"}
for k,v in c["volumes"].items():
    assert v["name"]=="loanhub-sandbox_"+k and not v.get("external") and not v.get("driver_opts")
for s in c["services"].values():
    assert not s.get("ports") and not s.get("privileged") and not s.get("network_mode")
    assert set(s["networks"])=={"isolated"}
for name in ("backend","seed","migrate"):
    e=c["services"][name]["environment"]
    assert e["DB_NAME"]=="loanhub_sandbox" and e["DB_HOST"]=="db" and e["SANDBOX_MODE"]=="true"
assert c["services"]["backend"]["environment"]["DB_USER"]=="sandbox_app"
'
"${compose[@]}" up -d --wait --wait-timeout 300
"${compose[@]}" exec -T backend python -c 'import json,urllib.request; r=urllib.request.Request("http://127.0.0.1:8000/api/v1/auth/login",data=json.dumps(dict(phone="sandbox@loanhub.co.ls",password="sandox123")).encode(),headers={"Content-Type":"application/json"}); assert urllib.request.urlopen(r,timeout=15).status==200'
printf '%s\n' "$release" > .current.sha.tmp
mv .current.sha.tmp .current.sha
echo "[LoanHub Sandbox] Healthy on $release"
