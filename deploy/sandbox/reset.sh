#!/usr/bin/env bash
# Install only after the sandbox stack has passed isolation and restore tests.
set -euo pipefail
umask 077
cd -- "$(dirname -- "$(realpath -- "${BASH_SOURCE[0]}")")"
[[ "${1:-}" == "--confirm-sandbox-reset" && "$#" == 1 ]] || {
  echo "Explicit --confirm-sandbox-reset required" >&2; exit 2;
}
[[ -f sandbox.env && -f compose.yaml ]] || exit 2
exec 9> .reset.lock
flock -n 9 || { echo "Sandbox reset already running" >&2; exit 1; }
# Disallow inherited Docker/Compose routing overrides. Use the local daemon.
unset DOCKER_CONTEXT DOCKER_HOST DOCKER_TLS_VERIFY DOCKER_CERT_PATH
unset COMPOSE_FILE COMPOSE_PROJECT_NAME COMPOSE_PROFILES COMPOSE_ENV_FILES
export DOCKER_HOST=unix:///var/run/docker.sock
compose=(docker compose --project-name loanhub-sandbox --project-directory "$PWD" --env-file "$PWD/sandbox.env" --file "$PWD/compose.yaml" --profile verified)
# Validate the entire resolved configuration without printing credentials.
# Reject alternate mounts, external resources, unrecognized services and names.
"${compose[@]}" config --format json | python3 -c '
import json, sys
c = json.load(sys.stdin)
def require(ok):
    if not ok:
        sys.exit("Sandbox reset refused: unexpected compose configuration")
require(c["name"] == "loanhub-sandbox")
require(set(c["services"]) == {"db","redis","migrate","role-bootstrap","seed","backend","frontend"})
require(set(c["volumes"]) == {"sandbox_db","sandbox_redis","sandbox_files"})
for key, vol in c["volumes"].items():
    require(vol.get("name") == "loanhub-sandbox_" + key and not vol.get("external") and not vol.get("driver_opts"))
require(set(c["networks"]) == {"isolated"})
require(c["networks"]["isolated"].get("internal") is True and not c["networks"]["isolated"].get("external"))
for key in ("migrate","seed","backend","role-bootstrap"):
    e = c["services"][key]["environment"]
    require(e.get("DB_NAME") == "loanhub_sandbox")
for key in ("migrate","seed","backend"):
    e = c["services"][key]["environment"]
    require(e.get("SANDBOX_MODE") == "true" and e.get("DB_HOST") == "db")
for svc in c["services"].values():
    require(not svc.get("privileged") and not svc.get("network_mode") and not svc.get("volumes_from") and not svc.get("container_name"))
'
# Inspect existing volumes before stopping anything. Never use down --volumes,
# prune, or remove volumes by a wildcard.
volumes=(loanhub-sandbox_sandbox_db loanhub-sandbox_sandbox_redis loanhub-sandbox_sandbox_files)
for vol in "${volumes[@]}"; do
  owner=$(docker volume inspect --format '{{ index .Labels "com.docker.compose.project" }}' "$vol")
  [[ "$owner" == loanhub-sandbox ]] || { echo "Unexpected volume owner: $vol" >&2; exit 1; }
done
"${compose[@]}" down --timeout 30
for vol in "${volumes[@]}"; do
  docker volume rm "$vol"
done
# Compose dependency gates run migrations, restricted role bootstrap and seed.
"${compose[@]}" up -d --wait --wait-timeout 300
echo "Sandbox reset stack startup completed; run application smoke checks."
