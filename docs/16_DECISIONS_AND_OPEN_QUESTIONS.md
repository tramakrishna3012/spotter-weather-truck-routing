# 16 — Architecture decision record and open questions

**Decision log rule:** Distinguish original assignment facts from proposed conventions. For a consequential change, write `ADR-###`, context, considered options, chosen option, consequences, owner/date, validation status. Do not silently rewrite established architecture.

## Summary decision register

| ID | Decision | Status / follow-up |
|---|---|---|
| ADR-001 | React + TypeScript + Django/DRF modular monolith | **Accepted & Implemented** — aligns with assessment React + Django stack (`backend/`, `frontend/`) |
| ADR-002 | HERE truck route alternatives (`transportMode=truck`, `alternatives=2`) | **Accepted & Implemented** — adapter behind port with fixture + live modes; owner to supply `HERE_API_KEY` for live verification |
| ADR-003 | Open-Meteo hourly forecast | **Accepted & Implemented** — adapter behind port with unit/freshness validation; verify commercial license before commercial deployment |
| ADR-004 | MapLibre GL JS plus separately licensed basemap | **Accepted & Implemented** — client renderer configured via `VITE_MAP_STYLE_URL` / `VITE_MAP_PUBLIC_TOKEN`; verify tile terms for production |
| ADR-005 | Scoring at conservative `<=10mi` internal resolution | **Accepted & Implemented** — configured via `INTERNAL_SCORING_MILES=10`; benchmark live provider quota/cost under load |
| ADR-006 | Display spacing `10/25/50mi` separate from scoring | **Accepted & Implemented** — display density decoupled from risk calculation; covered by invariance unit tests |
| ADR-007 | Exact overlapping threshold boundaries: half-open; strict `>` endpoints for No Travel | **Accepted & Implemented** — encoded in versioned backend risk policy (`risk-policy-v1`); verified by boundary unit tests |
| ADR-008 | Worst adjacent hourly weather bin used for safety classification | **Accepted & Implemented** — conservative fail-safe policy; documented tradeoff vs linear interpolation |
| ADR-009 | Exclude unknown weather and No Travel routes from recommendation | **Accepted & Implemented** — fail-closed safety behavior; never emits `recommended` on incomplete/blocked routes |
| ADR-010 | Request primary + 2 alternatives; render actual result count | **Accepted & Implemented** — consistent with HERE `alternatives=2`; UI renders 0/1/2/3 routes honestly with no placeholders |
| ADR-011 | Guest access with scoped opaque session token | **Accepted & Implemented** — no login needed for assessment; plans scoped to session/opaque access token |
| ADR-012 | Async job queue optional until measured | **Accepted & Superseded in detail by ADR-015** — synchronous default with opt-in Celery async toggle |
| ADR-013 | Stale weather invalidates safety recommendation | **Accepted & Implemented** — freshness checked against `WEATHER_CACHE_TTL_SECONDS` and forecast issuance timestamp |
| ADR-014 | Time slider's reference instant is explicit and stable (`departure_instant`) | **Accepted & Implemented (Resolved 2026-11-20)** — see full ADR-014 record below |
| ADR-015 | Synchronous planning default with optional Celery async toggle behind identical API contract | **Accepted & Implemented (Recorded 2026-11-20)** — see full ADR-015 record below |

---

## Implementation decision records

### ADR-014 — Forecast time slider reference instant (`departure_instant`)

- **Status:** Accepted & Implemented
- **Owner / Date:** Engineering & Architecture / 2026-11-20
- **Context:** The interactive 0–48 hour weather forecast heatmap slider (`GET /api/v1/plans/{plan_id}/forecast?hour_offset={0..48}`) requires an explicit, immutable reference timestamp so every slider tick maps unambiguously to a single UTC wall-clock instant (`valid_at`). Previously this was an open choice between `departure_instant` (the trip's requested departure timestamp) and `forecast_snapshot` (the weather model's issuance time or current wall clock).
- **Considered options:**
  1. `departure_instant` — `hour_offset = 0` equals the trip's `departure_at` (UTC), and `+H` equals `departure_at + H hours` up to `FORECAST_SLIDER_HOURS=48`.
  2. `forecast_snapshot` — `hour_offset = 0` equals the latest weather model issuance time (`issued_at`) or current server UTC hour.
- **Chosen option:** **Option 1 (`departure_instant`)**.
  - Every forecast slice response includes explicit reference metadata (`reference_type: "departure_instant"`, `reference_at` in UTC, `hour_offset`, and resolved `valid_at` in UTC).
  - The UI explicitly labels the heatmap slider as a **wall-clock exploratory forecast relative to departure** (`Departure + Hh`), visually and semantically distinct from the **route-arrival ETA weather scoring** used to classify checkpoints and select the recommended route.
  - Scrubbing the 0–48h slider updates only the exploratory weather overlay and **never** retroactively alters checkpoint ETA risk ratings, route eligibility, or the backend recommendation.
- **Consequences:**
  - *Positive:* Intuitive for dispatchers planning departures ("what does the corridor look like at departure, +6h, +24h?"), stable across re-fetches of the same plan, and aligns directly with trips scheduled in the near future.
  - *Tradeoff:* If a user schedules a departure near the end of `FORECAST_MAX_HORIZON_HOURS` (e.g., day 6 of a 7-day forecast), upper slider ticks beyond provider coverage return explicit out-of-range/incomplete coverage states (`422 forecast_out_of_range` or `coverage_complete=false`) rather than fabricated data.
- **Validation status:** Verified via backend forecast-slice endpoint tests, OpenAPI schema contract, and frontend slider timestamp/label rendering tests.

### ADR-015 — Synchronous planning default with optional Celery async execution toggle

- **Status:** Accepted & Implemented
- **Owner / Date:** Engineering & DevOps / 2026-11-20
- **Context:** Planning a trip involves calling HERE truck routing, sampling internal scoring checkpoints, fetching batched Open-Meteo hourly forecasts, and running the risk/ranking engine. In fixture mode and low-concurrency live deployments, this completes within a single HTTP request budget, avoiding the operational overhead of mandatory background workers. Under higher live traffic or long cross-country corridors with larger provider fanout, synchronous execution can approach HTTP worker timeout budgets.
- **Considered options:**
  1. Synchronous-only planning inside Django request workers.
  2. Mandatory Celery + Redis async worker pipeline for all environments (including local dev and fixture demos).
  3. Synchronous planning by default (`ENABLE_ASYNC_PLANNING=false`) with an opt-in Celery async toggle (`ENABLE_ASYNC_PLANNING=true`) behind the exact same REST contract.
- **Chosen option:** **Option 3 (Synchronous default with optional Celery async toggle)**.
  - When `ENABLE_ASYNC_PLANNING=false` (default for local dev, fixture mode, and lean MVP hosting): `POST /api/v1/plans` executes the planning service inline and returns `200 OK` with the completed `PlanResult` payload (and persists the plan so `GET /api/v1/plans/{plan_id}` works identically).
  - When `ENABLE_ASYNC_PLANNING=true` (production scale-out, started in Docker Compose via `--profile async` / `COMPOSE_PROFILES=async`): `POST /api/v1/plans` persists a queued job, dispatches it to the Celery worker (`celery -A config worker -l info --concurrency=${PLANNING_CONCURRENCY:-4}`), and returns `202 Accepted` with `status_url` and `poll_after_seconds`. The frontend handles both `200 OK` and `202 Accepted` + polling transparently against the same contract.
  - No fake async claims: operational docs and health/readiness endpoints clearly report the active execution mode.
- **Consequences:**
  - *Positive:* Zero-friction local setup and reliable single-container assessment deployment while preserving a clean, tested horizontal scale-out path without breaking API clients.
  - *Tradeoff:* Operators enabling `ENABLE_ASYNC_PLANNING=true` must provision Redis (`REDIS_URL`) and run at least one Celery worker process; startup validation fails fast if async mode is enabled without a valid broker configuration.
- **Validation status:** Configured in `.env.example`, `docker-compose.yml` (`async` profile), and backend planning service orchestration; verify live latency p95/p99 before enabling async in production.

---

## Open questions needing practical checks (not blockers to architecture docs)

1. Are the users always in a geography where HERE truck routing/coverage is adequate?
2. Is an account with paid/commercial weather use necessary now, or is it a noncommercial interview demonstration? *(See `docs/PREREQUISITES_AND_KEYS.md` for Open-Meteo licensing split.)*
3. What licensed basemap provider/style/token is acceptable and compatible with selected routing data terms? *(See `docs/PREREQUISITES_AND_KEYS.md` for vetted options.)*
4. Are truck dimensions/gross weight available? The assessment only specifies payload weight for weather risk; don't invent dimensions.
5. How far into the future may departure be scheduled, and how should out-of-forecast-horizon trips be handled? *(Currently bounded by `FORECAST_MAX_HORIZON_HOURS=168`; trips beyond horizon fail closed.)*
6. What exact model/time slice semantics will the 0–48h slider represent? *(Resolved in ADR-014: wall-clock offset from `departure_instant`, distinct from route ETA scoring.)*
7. For a deployed public demo, how much anonymous usage and provider billing budget is available?
8. What local/hosting runtime versions exist in the repository? *(Pinned to Python 3.11 + `uv` and Node 24 LTS in CI and Dockerfiles.)*
9. Is storing results across sessions required? If not, use short-lived guest results. *(Implemented as TTL-bounded ephemeral guest plans via `PLAN_RESULT_TTL_SECONDS=3600`.)*

## Review criteria for changes

Prefer reversible, measurable changes. Any architectural alteration must state its effect on risk correctness, user experience, provider costs, security, existing integrations and tests. The source assessment takes precedence over optional enterprise embellishments.
