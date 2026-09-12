# LoanHub Caddy reverse proxy

Production Caddy exposes two LoanHub hostnames from one VPS:

- `{$APP_DOMAIN}` (normally `loanhub.co.ls`) proxies to `frontend:3000`.
- `{$API_DOMAIN}` (normally `api.loanhub.co.ls`) proxies to `backend:8000`.
- `{$WWW_DOMAIN}` (normally `www.loanhub.co.ls`) redirects to the frontend apex domain.

The service is enabled by the Docker Compose `production` profile:

```bash
docker compose --profile production up -d
```

Caddy manages HTTPS certificates automatically. DNS A records for the apex, `api`, and `www` hostnames must point to the VPS before certificate issuance can complete.

Do not expose PostgreSQL or Redis publicly. The application ports 3000 and 8000 bind to loopback by default and Caddy reaches the services over the private Docker network.
