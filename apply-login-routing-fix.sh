#!/usr/bin/env bash
set -euo pipefail

FRONTEND_ROOT="apps/frontend"

if [[ ! -d "$FRONTEND_ROOT" ]]; then
    echo "Could not find $FRONTEND_ROOT"
    exit 1
fi

LOGIN_FILE="$(
    grep -RIl \
        --include='*.tsx' \
        'loginUser\.fulfilled\.match' \
        "$FRONTEND_ROOT/app" |
    head -n 1
)"

if [[ -z "${LOGIN_FILE:-}" ]]; then
    echo "Could not locate the greetings/login page."
    echo "Expected a file containing loginUser.fulfilled.match"
    exit 1
fi

echo "Login page found: $LOGIN_FILE"

python3 - "$LOGIN_FILE" <<'PY'
from pathlib import Path
import sys

path = Path(sys.argv[1])
source = path.read_text(encoding="utf-8")

if "window.location.replace(targetPath)" in source:
    print(f"Post-login hard navigation already exists in {path}")
    raise SystemExit(0)

safe_redirect = (
    "router.replace("
    "safeRequestedPath ?? "
    "getDashboardRoute(result.payload.user.role)"
    ");"
)

direct_redirect = (
    "router.replace("
    "getDashboardRoute(result.payload.user.role)"
    ");"
)

safe_replacement = """const targetPath =
                safeRequestedPath ??
                getDashboardRoute(result.payload.user.role);

            /*
             * A full navigation is intentional here.
             *
             * Next.js client routing can still hold route metadata and
             * JavaScript chunks from the previous Docker deployment.
             * Reloading the document guarantees that /company uses the
             * current build and keeps the authenticated refresh cookie.
             */
            router.prefetch(targetPath);
            window.location.replace(targetPath);"""

direct_replacement = """const targetPath =
                getDashboardRoute(result.payload.user.role);

            /*
             * Force the authenticated dashboard to load from the current
             * production build instead of reusing a stale client route.
             */
            router.prefetch(targetPath);
            window.location.replace(targetPath);"""

if safe_redirect in source:
    source = source.replace(
        safe_redirect,
        safe_replacement,
        1,
    )
elif direct_redirect in source:
    source = source.replace(
        direct_redirect,
        direct_replacement,
        1,
    )
else:
    raise SystemExit(
        "The login success block was found, but its redirect statement "
        "does not match the expected LoanHub implementation."
    )

path.write_text(source, encoding="utf-8")
print(f"Updated {path}")
PY

PROXY_FILE="$FRONTEND_ROOT/proxy.ts"

if [[ -f "$PROXY_FILE" ]]; then
    python3 - "$PROXY_FILE" <<'PY'
from pathlib import Path
import sys

path = Path(sys.argv[1])
source = path.read_text(encoding="utf-8")

updated = source.replace(
    'new URL("/login", request.url)',
    'new URL("/greetings", request.url)',
)

updated = updated.replace(
    "new URL('/login', request.url)",
    "new URL('/greetings', request.url)",
)

if updated != source:
    path.write_text(updated, encoding="utf-8")
    print(f"Updated protected-route redirect in {path}")
else:
    print(f"No /login proxy redirect found in {path}")
PY
fi

echo
echo "Checking for remaining protected redirects to /login..."

grep -RIn \
    --include='*.ts' \
    --include='*.tsx' \
    '"/login"\|'\''/login'\''' \
    "$FRONTEND_ROOT" \
    --exclude-dir=node_modules \
    --exclude-dir=.next || true

echo
echo "Patch applied."
echo "Review the changes with:"
echo "  git diff -- apps/frontend"
