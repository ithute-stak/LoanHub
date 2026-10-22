# LoanHub cache performance — Phase 1 baseline and audit

**Status:** Source-code audit complete; production timing and cache hit ratios **not measured**.
**Baseline revision:** `main` at Phase 1 branch creation (2026-10-22).
**Objective:** Identify redundant reads, cache invalidation churn and frontend reloading without changing transaction semantics.

## Current implementation verified

| Layer | Location | Observed behaviour |
|---|---|---|
| Browser | `apps/frontend/lib/http-cache.ts` | Redux-backed Axios GET cache; concurrent request deduplication; tenant/user/role-scoped entries; path-specific TTL and tag invalidation |
| Browser provider | `apps/frontend/provider/appDataProvider.tsx` | Holds shared directory and financial lists; listens for database commit events and refreshes affected resources |
| Realtime | `apps/frontend/provider/realtimeProvider.tsx` | Invalidates tags or whole scopes and calls `router.refresh()` on selected remote events |
| API | `apps/backend/core/response_cache.py` | Redis-backed JSON response cache; short TTLs, response size cap, bypass paths; cached response indicators |
| Backend telemetry | `apps/backend/core/observability.py` | Records HTTP request duration and exposes Prometheus metrics when configured |
| Deployment | `compose.yaml` | Redis 7-alpine, backend `REDIS_URL=redis://redis:6379/0` |

### Configured TTL baseline (not production measurements)

| Category | Frontend | Backend |
|---|---:|---:|
| Financial read paths | 10 sec | 10 sec |
| Summaries and analytics | 20 sec (+ 5 sec stale window) | 20 sec |
| Directories | 60 sec (+ 15 sec stale window) | 60 sec |
| Reference data | 300 sec (+ 60 sec stale window) | 300 sec |
| General reads | 30 sec | configured 30 sec |

**Note:** The frontend policy uses path matching; not every endpoint is guaranteed to map to the same category in both implementations. Excluded or bypassed responses are not cache hits.

## Identified investigation priorities

1. **Broad backend invalidation:** `TenantResponseCacheMiddleware` bumps a company/user generation after successful API write responses. This can invalidate *unrelated* entries, increasing miss rates and PostgreSQL traffic. Study authorization and commit boundaries before narrowing it.
2. **Repeated real-time refreshes:** WebSocket commits can trigger cache invalidation, AppData reload, and `router.refresh()`. Count duplicate GETs per commit/route.
3. **Cache misses under concurrency:** Backend Redis cache does not currently demonstrate single-flight GET filling across workers. Measure simultaneous misses during busy periods.
4. **Cache policy matching:** Both layers use path-substring policies. Check endpoint-by-endpoint TTL classification and exclusions.
5. **Frontend correctness:** Preserve form state, filters, sorting, and scroll position; measure loading indicators and stale responses after a write.
6. **Safety:** Verify cache isolation across user, company, role, permissions and query parameters; verify write invalidation and no authorization or financial-decision reuse.
7. **Redis fallback:** Verify behaviour when Redis is slow/unavailable, including additional latency from connection and read timeouts.

## Safe measurement plan

Production server access is not connected to this chat. **Do not report latency percentiles, DB query reductions or hit rates until measured.**

* Record baseline over representative dashboard, directory, loan history, payment history, CDAS history and registration workflows.
* Measure endpoint p50/p95/p99 server latency from structured `http_request` logs or metrics, separated by route and status.
* Measure client request count, waterfall, cache `X-LoanHub-Client-Cache` HIT/STALE indicators where applicable, and navigation time with browser developer tools.
* Record server `X-LoanHub-Server-Cache` HIT/MISS/BYPASS counts and percentage by route. These are already response headers; **do not export sensitive response bodies**.
* Capture PostgreSQL `pg_stat_statements` if enabled, query count/mean latency/total time for candidate endpoints, connection pool and lock wait metrics.
* Record Redis `INFO stats` keyspace hit/miss counters, memory, evictions and command latency; note these aggregate *all* Redis usage, not exclusively this response cache.
* Compare no-change repeat navigation, one remote mutation, concurrent 10/50 users, and worker failure scenarios.
* Record CPU, RAM, container restarts and worker call timings for Python, Rust, Go and Java.

### Proposed measurement sheet

| Route/workflow | Requests per visit | Backend p50/p95 ms | Frontend p50/p95 ms | Client HIT/STALE | Server HIT/MISS/BYPASS | Database queries per visit | Notes |
|---|---:|---|---|---|---|---:|---|
| Company dashboard | TBD | TBD | TBD | TBD | TBD | TBD | |
| Client directory, repeat filters | TBD | TBD | TBD | TBD | TBD | TBD | |
| Loan history | TBD | TBD | TBD | TBD | TBD | TBD | |
| Payment history | TBD | TBD | TBD | TBD | TBD | TBD | |
| Legacy cashout | TBD | TBD | TBD | TBD | TBD | TBD | |
| CDAS history | TBD | TBD | TBD | TBD | TBD | TBD | |

## Acceptance gates for Phase 1

- [x] Inventory cache implementations and observability hooks.
- [x] Identify likely invalidation and duplicate-fetch risk paths.
- [x] Define safety-focused baseline collection and candidate workflows.
- [ ] Collect production or representative load metrics (requires accessible environment).
- [ ] Rank bottlenecks using measured impact, not assumptions.

**Phase 2 should begin with isolation and committed-write correctness tests before narrowing invalidation or increasing TTLs.**
