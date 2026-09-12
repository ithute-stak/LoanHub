# Docker files for `apps/backend` and `apps/frontend`

1. Extract this package at the repository root.
2. Do not extract it inside `apps/`.
3. Run:

```bash
chmod +x scripts/*.sh apps/backend/docker/entrypoint.sh docker/start-all-in-one.sh
./scripts/docker-init.sh
./scripts/docker-up.sh
```

See `docs/DOCKER_DEPLOYMENT.md` for deployment and backup instructions.
