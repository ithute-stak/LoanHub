#!/usr/bin/env sh
set -eu

: "${EDGE_PUBLIC_IP:?EDGE_PUBLIC_IP is required}"
: "${TLS_EMAIL:?TLS_EMAIL is required}"

COMPOSE_FILES="-f compose.yaml -f compose.edge-nginx.yml"
compose() {
  # shellcheck disable=SC2086
  docker compose --env-file .env.production $COMPOSE_FILES --profile production "$@"
}

# Only request names that currently resolve to this VPS. This prevents one stale
# product DNS record from invalidating the entire SAN certificate order.
candidates="
ithute.co.ls
www.ithute.co.ls
panel.ithute.co.ls
api.ithute.co.ls
auth.ithute.co.ls
push.ithute.co.ls
realtime.ithute.co.ls
groupware.ithute.co.ls
pay.ithute.co.ls
api.pay.ithute.co.ls
portal.pay.ithute.co.ls
mail.ithute.co.ls
${APP_DOMAIN:-loanhub.co.ls}
${WWW_DOMAIN:-www.loanhub.co.ls}
${API_DOMAIN:-api.loanhub.co.ls}
${SANDBOX_APP_DOMAIN:-sandbox.loanhub.co.ls}
${SANDBOX_API_DOMAIN:-api-sandbox.loanhub.co.ls}
"

domains=""
seen=""
for domain in $candidates; do
  [ -n "$domain" ] || continue
  case " $seen " in
    *" $domain "*) continue ;;
  esac
  seen="$seen $domain"

  if getent ahostsv4 "$domain" 2>/dev/null | awk '{print $1}' | grep -Fxq "$EDGE_PUBLIC_IP"; then
    domains="$domains $domain"
    echo "TLS candidate verified: $domain -> $EDGE_PUBLIC_IP"
  else
    echo "Skipping TLS name that does not resolve to this VPS: $domain" >&2
  fi
done

for required in auth.ithute.co.ls pay.ithute.co.ls api.pay.ithute.co.ls portal.pay.ithute.co.ls mail.ithute.co.ls; do
  case " $domains " in
    *" $required "*) ;;
    *) echo "Required production hostname is not pointed at $EDGE_PUBLIC_IP: $required" >&2; exit 1 ;;
  esac
done

set --
for domain in $domains; do
  set -- "$@" -d "$domain"
done

# Standalone ACME owns port 80 only during issuance. The command is idempotent:
# Certbot keeps a non-expiring certificate when the requested SAN set is the
# same, and --expand adds newly activated Ithute names without a second cert.
docker ps \
  --filter "label=com.docker.compose.project=${COMPOSE_PROJECT_NAME:-loanhub}" \
  --filter 'label=com.docker.compose.service=caddy' \
  -q | xargs -r docker rm -f

docker ps \
  --filter "label=com.docker.compose.project=${COMPOSE_PROJECT_NAME:-loanhub}" \
  --filter 'label=com.docker.compose.service=edge-nginx' \
  -q | xargs -r docker rm -f

compose run --rm --no-deps -p 80:80 --entrypoint certbot certbot \
  certonly --standalone --non-interactive --agree-tos \
  --email "$TLS_EMAIL" --cert-name ithute-edge --expand "$@"

compose run --rm --no-deps --entrypoint /bin/sh certbot \
  -c 'test -s /etc/letsencrypt/live/ithute-edge/fullchain.pem && test -s /etc/letsencrypt/live/ithute-edge/privkey.pem'
