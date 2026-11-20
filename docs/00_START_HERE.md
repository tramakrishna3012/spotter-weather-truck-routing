# 00 — Start Here: project bootstrap and human prerequisites

## Required first actions for coding agent

1. Inspect repo before adding a package. Confirm if code exists and which conventions, scripts, constructor patterns and services are already present. Write a short inventory and identify conflicts.
2. Verify original PDF and `docs/04_DESIGN.md`. Create a requirement-to-test checklist from `docs/01_REQUIREMENTS_TRACEABILITY.md`.
3. Check provider access without leaking a token. Configure local `.env` from `.env.example` and validate required values at startup; don't commit secrets.
4. Identify existing API, tests, Docker, database and CI before introducing replacements.
5. Implement proof-oriented vertical slices and measure actual quality; report open issues without disguising them.

## Preload list for the human owner

**Needed for live route/weather functionality:** HERE account + truck-routing API key; approved weather provider (Open-Meteo forecast is proposed); suitable licensed map tile/style provider or a provider with permitted usage; local development Node.js and Python; PostgreSQL and Redis (Docker Compose is a convenient option). External billing/licensing varies. A geocoding provider may be HERE Geocoding & Search if natural-language origin/destination are used. For hosting, choose one environment that supports Python API + worker + Redis + PostgreSQL and static frontend deployment.

**Not needed for assessment MVP:** Google login, GitHub login, paid animations, Three.js, enterprise SSO, billing, fleet/tenant dashboards, Kubernetes, Kafka, complex permissions, a separate analytics vendor, a paid telemetry provider.

**Never send API keys into chat or check them into git.** Store them locally in `.env` or secret manager; the agent should reference names only.

## Recommended working stack

| Layer | Suggested choice | Why |
|---|---|---|
| UI | React + TypeScript + Vite | Predictable SPA, rich map composition |
| Styling | Tailwind CSS + semantic CSS custom properties | Design token consistency, minimal bespoke CSS |
| Accessible primitives | Radix UI where justified | Keyboard-safe dialogs/panels; avoid library bloat |
| Client data | TanStack Query | Caching, cancellation, background state |
| Map | MapLibre GL JS | Efficient line/point/heatmap rendering |
| Frontend tests | Vitest, React Testing Library, Playwright | Unit + interaction + E2E |
| API | Django + DRF | Existing assessment requirement, validation, maintainability |
| API typing | DRF serializers + generated OpenAPI where feasible | Contract consistency |
| Background jobs | Celery + Redis, if necessary | Long provider fanout and bounded worker concurrency |
| Data | PostgreSQL | Strong transactional storage; optional PostGIS only if spatial queries require it |
| HTTP | httpx (async for bounded fanout) | Timeouts, retries, typed adapters |
| Python tests | pytest + pytest-django | Deterministic logic/provider mocking |
| Deployment | Managed static web + Python API/worker + Postgres/Redis | Avoid orchestration complexity until justified |

Versions should be selected after checking the latest stable packages and compatibility, then pinned using lockfiles. Do not introduce multiple state libraries, duplicate API clients or redundant component systems.

## Working environments

- `local fixture`: explicit `DATA_MODE=fixture`, UI marked **Sample data**; no network dependency.
- `local live`: `DATA_MODE=live`, validated credentials and provider calls.
- `staging`: production-like config, test provider budgets, redacted logs.
- `production`: live only; missing credentials should fail startup or produce a safe unavailable state, never silently switch to fixtures.

## Ready-to-code preflight

- [ ] Requirements read and traced.
- [ ] Existing code inspected and reusable modules catalogued.
- [ ] Required providers chosen and accounts activated, or explicit fixture-only limitation agreed.
- [ ] Route and weather API quotas/terms checked.
- [ ] `.env` configured without committing secrets.
- [ ] Tests, formatting and CI command paths identified.
- [ ] Start sequence and milestones documented.
