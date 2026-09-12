# syntax=docker/dockerfile:1.7

ARG PNPM_VERSION=11.21.0

FROM node:22-alpine AS dependencies
ARG PNPM_VERSION
WORKDIR /app
ENV PNPM_HOME=/pnpm \
    PATH=/pnpm:$PATH
RUN corepack enable \
    && corepack prepare "pnpm@${PNPM_VERSION}" --activate
COPY package.json pnpm-lock.yaml pnpm-workspace.yaml ./
RUN --mount=type=cache,id=loanhub-pnpm-store,target=/pnpm/store \
    --mount=type=cache,id=loanhub-pnpm-metadata,target=/root/.cache/pnpm \
    pnpm config set store-dir /pnpm/store \
    && pnpm config set network-concurrency 4 \
    && pnpm config set fetch-retries 5 \
    && pnpm config set fetch-retry-mintimeout 20000 \
    && pnpm config set fetch-retry-maxtimeout 120000 \
    && pnpm config set fetch-timeout 600000 \
    && pnpm install --frozen-lockfile --prefer-offline

FROM dependencies AS production-dependencies
RUN pnpm prune --prod

FROM dependencies AS builder
ENV NEXT_TELEMETRY_DISABLED=1
ARG NEXT_PUBLIC_API_URL=http://localhost:8000/api/v1
ENV NEXT_PUBLIC_API_URL=${NEXT_PUBLIC_API_URL}
COPY . .
RUN pnpm typecheck && pnpm build

FROM node:22-alpine AS runner
WORKDIR /app
ENV NODE_ENV=production \
    NEXT_TELEMETRY_DISABLED=1 \
    PORT=3000 \
    HOSTNAME=0.0.0.0

RUN addgroup --system --gid 1001 nodejs \
    && adduser --system --uid 1001 nextjs

COPY --from=builder --chown=nextjs:nodejs /app/public ./public
COPY --from=builder --chown=nextjs:nodejs /app/.next/standalone ./
# Next.js standalone tracing can leave pnpm symlinks whose targets are not copied
# into the standalone tree. Overlay the production-only dependency tree so those
# symlinks resolve at runtime without shipping development dependencies.
COPY --from=production-dependencies --chown=nextjs:nodejs /app/node_modules ./node_modules
COPY --from=builder --chown=nextjs:nodejs /app/.next/static ./.next/static

USER nextjs
EXPOSE 3000

# Boot the actual production server during the image build. This catches broken
# standalone dependency graphs (such as missing @swc/helpers) before an image can
# be published to GHCR or deployed to the VPS.
RUN set -eux; \
    node server.js >/tmp/loanhub-frontend-smoke.log 2>&1 & \
    pid=$!; \
    ready=0; \
    for attempt in 1 2 3 4 5 6 7 8 9 10 11 12 13 14 15; do \
        if wget -qO- http://127.0.0.1:3000/ >/dev/null 2>&1; then \
            ready=1; \
            break; \
        fi; \
        if ! kill -0 "$pid" 2>/dev/null; then \
            break; \
        fi; \
        sleep 1; \
    done; \
    if [ "$ready" -ne 1 ]; then \
        cat /tmp/loanhub-frontend-smoke.log >&2 || true; \
        kill "$pid" 2>/dev/null || true; \
        wait "$pid" 2>/dev/null || true; \
        exit 1; \
    fi; \
    kill "$pid"; \
    wait "$pid" 2>/dev/null || true; \
    rm -f /tmp/loanhub-frontend-smoke.log

HEALTHCHECK --interval=30s --timeout=5s --start-period=40s --retries=5 \
    CMD wget -qO- http://127.0.0.1:3000/ >/dev/null || exit 1

CMD ["node", "server.js"]
