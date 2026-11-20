# 13 — Implementation plan: sequenced, testable work packages

## Phase 0 — Preflight (mandatory)

- Inspect existing repository; list functioning parts and reusable constructors/classes. Confirm framework/versions and deployment constraints.
- Read PDF, AGENTS and design spec. Confirm provider accounts and license.
- Create `docs/16_DECISIONS_AND_OPEN_QUESTIONS.md` ADR updates for decisions not established in source.
- Define env parsing and secret handling; add lint/test skeleton.

**Exit:** proof of dependency readiness, repo inventory, planned diffs. Do not rewrite an existing codebase just to fit a template.

## Phase 1 — Domain engine (P0)

- Define typed trip, route, checkpoint, forecast, status and risk models.
- Implement unit normalization, versioned boundaries, wind/load overrides, missing weather semantics.
- Implement distance-based checkpoint sampling + ETA + weighted risk segment attribution.
- Implement eligibility filtering and lexicographic ranking.
- Add all critical unit tests before UI polish.

**Exit:** deterministic tests for threshold, mileage, time, unit conversion and no-eligible cases.

## Phase 2 — External adapters + plan API (P0)

- HERE truck routing + optional HERE geocoding behind ports.
- Open-Meteo hourly data adapter with batched queries, unit and timestamp metadata, license choice.
- Django serializers/endpoints, normalized DTO, 0..N routes and safe errors.
- Add Redis cache and optional Celery if provider latency requires async; idempotency and queue limits.
- Add integration/contract tests. No provider secret in repo.

**Exit:** real (credential-dependent) API journey works or an explicit fixture-mode implementation is labeled; provider failure path verified.

## Phase 3 — Premium frontend foundation (P0)

- Extract design tokens/typography and component primitives from `04_DESIGN.md`.
- Implement planner inputs and selection, validation, state choreography, skeletons and responsive map-first workspace.
- Connect frontend with typed API client and server-state flow; no invented values.
- Implement routing lines, selected segments, checkpoint popover and accurate route comparison.

**Exit:** full input -> response -> comparison journey on desktop and mobile.

## Phase 4 — Weather corridor + UI finishing (P0)

- 0–48h slider with explicit reference timestamps, point/corridor heatmap, coverage gaps and correct attribution.
- Keep map mounted and update source data; throttle slider and cache nearby frames.
- Apply subtle depth and purposeful transitions, not literal 3D. Reduced-motion, keyboard and accessible table/list equivalent.
- Test on actual slower hardware; refine typography, states, overflow and layer ordering.

**Exit:** actual map and heatmap smooth with measured evidence, including blocked/unknown cases.

## Phase 5 — Hardening, scale and delivery (P1)

- Security: provider keys, TLS, scoped plans, quotas, no SSRF, CORS/CSRF, log redaction and error handling.
- Database/cache/worker migrations and operational runbooks. Add metrics for provider latency, plan status, queue, error/coverage.
- CI with frontend/backend test/build; contract tests; reliability and load simulation.
- Hosted app, complete README, env list, sample screenshots **labeled**, 5–10min Loom based on actual implementation.

**Exit:** `docs/17_ACCEPTANCE_CHECKLIST.md` passes or each non-pass is clearly documented with evidence/blocker.

## Don't prematurely build

Auth/fleet/admin/multi-tenant, Kafka, Kubernetes, heavy 3D/WebGL effects, animated marketing site, traffic prediction, payments, GPS tracking. Build only when user requirements or measured needs justify them.
