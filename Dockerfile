# syntax=docker/dockerfile:1.7

ARG NODE_VERSION=24.18.0
ARG PYTHON_VERSION=3.14


# ============================================================
# Stage 1: Build the Next.js frontend
# ============================================================
FROM node:${NODE_VERSION}-bookworm-slim AS frontend-builder

ENV CI=true
ENV NEXT_TELEMETRY_DISABLED=1

WORKDIR /build/frontend

RUN corepack enable \
    && corepack prepare pnpm@11.17.0 --activate

COPY apps/frontend/package.json ./
COPY apps/frontend/pnpm-lock.yaml ./

# Use a deterministic non-interactive build-script approval file.
COPY docker/frontend-pnpm-workspace.yaml ./pnpm-workspace.yaml

RUN echo "=== Docker pnpm configuration ===" \
    && cat pnpm-workspace.yaml \
    && echo "=================================" \
    && pnpm config set store-dir /pnpm/store \
    && pnpm config delete minimum-release-age || true \
    && pnpm config set minimum-release-age 0 \
    && pnpm install --frozen-lockfile

# Copy the frontend source.
COPY apps/frontend/ ./

# The source copy may contain another pnpm-workspace.yaml, so restore
# the Docker-specific configuration before running pnpm build.
COPY docker/frontend-pnpm-workspace.yaml ./pnpm-workspace.yaml

ARG NEXT_PUBLIC_API_URL=/api/v1
ENV NEXT_PUBLIC_API_URL=${NEXT_PUBLIC_API_URL}

RUN echo "=== pnpm configuration used during build ===" \
    && cat pnpm-workspace.yaml \
    && echo "============================================" \
    && pnpm build \
    && if [ -d public ]; then \
         cp -r public .next/standalone/public; \
       fi \
    && mkdir -p .next/standalone/.next \
    && cp -r .next/static .next/standalone/.next/static

# ============================================================
# Stage 2: Build the Python environment
# ============================================================
FROM python:${PYTHON_VERSION}-slim-bookworm AS backend-builder

ENV VIRTUAL_ENV=/opt/venv
ENV PATH="${VIRTUAL_ENV}/bin:${PATH}"

RUN apt-get update \
    && apt-get install -y --no-install-recommends \
       build-essential \
       gcc \
       libpq-dev \
    && rm -rf /var/lib/apt/lists/*

RUN python -m venv "${VIRTUAL_ENV}" \
    && pip install --upgrade pip setuptools wheel

WORKDIR /build/backend

COPY apps/backend/requirements.txt ./

RUN pip install --no-cache-dir -r requirements.txt


# ============================================================
# Stage 3: Final LoanHub runtime
# ============================================================
FROM python:${PYTHON_VERSION}-slim-bookworm AS runtime

ARG APP_VERSION=development

LABEL org.opencontainers.image.title="LoanHub"
LABEL org.opencontainers.image.description="LoanHub Next.js and FastAPI application"
LABEL org.opencontainers.image.source="https://github.com/ithutesolhub-sketch/LoanHub"
LABEL org.opencontainers.image.version="${APP_VERSION}"

ENV PYTHONUNBUFFERED=1
ENV PYTHONDONTWRITEBYTECODE=1
ENV NEXT_TELEMETRY_DISABLED=1
ENV PATH="/opt/venv/bin:${PATH}"

RUN apt-get update \
    && apt-get install -y --no-install-recommends \
       supervisor \
       curl \
       ca-certificates \
       libpq5 \
       libstdc++6 \
       libatomic1 \
    && rm -rf /var/lib/apt/lists/*

# Copy only the Node runtime binary. Next standalone already contains
# the required JavaScript dependencies.
COPY --from=frontend-builder /usr/local/bin/node /usr/local/bin/node

# Python virtual environment.
COPY --from=backend-builder /opt/venv /opt/venv

# Backend source.
COPY apps/backend/ /app/backend/

# Next.js standalone production output.
COPY --from=frontend-builder \
    /build/frontend/.next/standalone/ \
    /app/frontend/

COPY docker/supervisord.conf \
    /etc/supervisor/conf.d/loanhub.conf

COPY docker/entrypoint.sh \
    /usr/local/bin/loanhub-entrypoint

RUN chmod +x /usr/local/bin/loanhub-entrypoint \
    && mkdir -p \
       /app/backend/media \
       /app/backend/uploads \
       /app/backend/secrets

WORKDIR /app/backend

EXPOSE 3000
EXPOSE 8000

HEALTHCHECK \
    --interval=30s \
    --timeout=5s \
    --start-period=60s \
    --retries=5 \
    CMD curl -fsS http://127.0.0.1:8000/health \
        || curl -fsS http://127.0.0.1:8000/docs >/dev/null \
        || exit 1

ENTRYPOINT ["/usr/local/bin/loanhub-entrypoint"]