# Safe `pull loanhub latest`

The production deployment helper is now the authoritative release selector for LoanHub.

A VPS wrapper such as `/usr/local/bin/pull` must not independently choose a historical GHCR tag and then pass that SHA to LoanHub. For the `latest` mode, delegate the selection unchanged:

```bash
exec sudo /opt/loanhub/scripts/deploy-production-manual.sh latest
```

For an explicitly requested SHA, pass that exact SHA:

```bash
exec sudo /opt/loanhub/scripts/deploy-production-manual.sh "$release_sha"
```

The helper validates release ancestry against `/opt/loanhub/releases/current.sha`, checks successful release-image workflow runs, verifies both GHCR images, and checks live Alembic revision compatibility before it can replace application containers.

This keeps the generic `pull` command convenient while ensuring that the product-specific deployment policy cannot be bypassed by stale release discovery logic in a VPS wrapper.
