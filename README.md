# Spotter — AI Project Handoff Pack

**Purpose:** Copy these files into the root of your new or existing Spotter project, then ask your coding agent to follow `AGENTS.md` and `docs/15_AI_EXECUTION_PROMPT.md`. This pack is a **design and engineering handoff**, not a finished application. No live API credentials, production services, working frontend/backend, or deployments are included.

**Product:** Weather-Aware Truck Routing — React + Django full-stack assessment. The authoritative original requirements are in [`reference/fs-assessment-spotter.pdf`](reference/fs-assessment-spotter.pdf). The existing premium UI design specification is preserved in [`docs/04_DESIGN.md`](docs/04_DESIGN.md). Other engineering documents in this pack are fresh proposals derived from those inputs; they should be validated against the working repository and external providers as implementation proceeds.

## Read in this order

1. `AGENTS.md` — non-negotiable instructions for every coding agent.
2. `docs/00_START_HERE.md` — required human setup and definition of success.
3. `docs/01_REQUIREMENTS_TRACEABILITY.md` — original requirement-to-proof mapping.
4. `docs/02_ARCHITECTURE.md` and `docs/06_RISK_AND_RECOMMENDATION.md` — system shape and safety-critical algorithm.
5. `docs/04_DESIGN.md` and `docs/03_FRONTEND_ENGINEERING.md` — art direction and build constraints.
6. `docs/13_IMPLEMENTATION_ROADMAP.md`, `docs/12_TEST_STRATEGY.md`, `docs/17_ACCEPTANCE_CHECKLIST.md` — delivery plan and evidence.
7. `docs/15_AI_EXECUTION_PROMPT.md` — pasteable kickoff prompt.

## Included documents

| File | Why it exists |
|---|---|
| `AGENTS.md` | Cross-agent rules; reuse existing code, no invented weather or unsafe recommendations |
| `CLAUDE.md`, `.github/copilot-instructions.md` | Thin pointers for agent entry points; no competing instructions |
| `docs/00_START_HERE.md` | Preflight, credentials, local setup order |
| `docs/01_REQUIREMENTS_TRACEABILITY.md` | Every assessment requirement mapped to tests |
| `docs/02_ARCHITECTURE.md` | HLD, runtime boundaries, sequence and failure design |
| `docs/03_FRONTEND_ENGINEERING.md` | React map-first rendering, state, component conventions |
| `docs/04_DESIGN.md` | Existing 800-line premium UI/UX design system |
| `docs/05_USER_FLOWS.md` | Detailed input-to-recommendation experience and state handling |
| `docs/06_RISK_AND_RECOMMENDATION.md` | Units, exact boundaries, checkpoint sampling, risk miles, ranking |
| `docs/07_API_CONTRACT.md` | Proposed versioned Django endpoint payloads and errors |
| `docs/08_DATA_MODEL.md` | Proposed persistence, TTL, privacy and caching models |
| `docs/09_INTEGRATIONS_AND_SERVICES.md` | HERE, weather, geocoding, basemap, costs, alternatives and licensing |
| `docs/10_SECURITY.md` | Input validation, keys, auth assumptions, abuse protection |
| `docs/11_PERFORMANCE.md` | Frontend performance budgets and backend concurrency |
| `docs/12_TEST_STRATEGY.md` | Deterministic unit, integration, contract, E2E and load tests |
| `docs/13_IMPLEMENTATION_ROADMAP.md` | Phased execution sequence and definitions of done |
| `docs/14_DEPLOYMENT_AND_OPERATIONS.md` | Local, staging, production and failure recovery |
| `docs/15_AI_EXECUTION_PROMPT.md` | Copy/paste prompt to start end-to-end implementation |
| `docs/16_DECISIONS_AND_OPEN_QUESTIONS.md` | Explicit assumptions and decision record |
| `docs/17_ACCEPTANCE_CHECKLIST.md` | Objective completion criteria |
| `docs/18_OBSERVABILITY.md` | Logs, metrics, tracing, alerts and privacy |
| `docs/19_ACCESSIBILITY.md` | Keyboard, labels, map alternatives, contrast and reduced motion |
| `docs/20_DEMO_AND_HANDOFF.md` | README, deployment and 5–10 minute Loom plan |
| `docs/21_CODING_STANDARDS.md` | SOLID, provider ports, reuse, review and code gates |
| `docs/22_SERVICE_SETUP_CHECKLIST.md` | What the human must pre-provision, in priority order |
| `.env.example` | Environment variable names only, **no secrets** |
| `reference/fs-assessment-spotter.pdf` | Original assessment (unchanged) |

## Workflow

```text
COPY handoff files into repo
  -> REVIEW existing repository and environment
  -> CONFIGURE provider accounts and .env (never commit)
  -> BUILD first working vertical slice
  -> PROVE risk engine with tests
  -> COMPLETE map and responsive UI
  -> HARDEN + TEST + DEPLOY + DEMO
```

### Critical distinctions

- Request three route options, but show **fewer** when the provider returns fewer distinct valid truck routes. Never fabricate an alternative.
- Risk rules are **given assessment constants**; operational values such as provider URLs, timeout budgets and sampling defaults must be centrally configurable.
- Weather forecast predictions are uncertain. Never claim a route is guaranteed safe.
- Forecast availability and route coverage determine whether a route can be recommended. Incomplete coverage must not silently rank as Low.
- A user-selected **10 / 25 / 50 mile display sampling** must not weaken the backend's conservative scoring resolution.
- The assessment does **not** require billing, fleet administration, full multi-tenant accounts, or a microservice fleet. Avoid scope creep.

## Official provider docs (verify current account conditions before production)

- HERE truck routing: https://docs.here.com/routing/docs/routing-v8-truck-routing
- HERE route calculation and alternatives: https://docs.here.com/routing/reference/routing-api-v8-calculateroutes
- Open-Meteo forecast: https://open-meteo.com/en/docs
- Open-Meteo plans and commercial restrictions: https://open-meteo.com/en/pricing
- MapLibre heatmap example: https://maplibre.org/maplibre-gl-js/docs/examples/create-a-heatmap-layer/

> **Stop condition:** Do not claim this handoff is a working app. Implement, verify and document actual results before declaring the project complete.
