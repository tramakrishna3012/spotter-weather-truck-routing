# 22 — Preload accounts, services, API keys and developer tools

This is the owner's procurement/setup checklist. **Never paste real secrets into an AI prompt.** Create accounts through provider consoles, keep keys in local `.env` / deployed secret manager, and restrict each key to the intended environment.

## Absolutely needed to exercise real assessment end-to-end

| Priority | What to provision | Specific output to prepare | Why |
|---|---|---|---|
| P0 | HERE developer project and Routing API v8 | Backend `HERE_API_KEY` | Truck-aware alternative routes |
| P0 | Geocoding provider (HERE recommended) | Access to HERE Geocoding & Search or approved substitute | Convert typed places to coordinates |
| P0 | Weather provider (Open-Meteo recommended) | Approved live endpoint + `OPEN_METEO_API_KEY` if paid plan | Hourly wind/rain/snow forecasts |
| P0 | Basemap style and tiles (licensed) | Publicly permitted `VITE_MAP_STYLE_URL` and optional browser token | MapLibre renderer requires a tile/style source |
| P0 | Node.js with package manager + Python + Git | Installed toolchain, with package versions determined after repo audit | Build frontend/backend |
| P0 | GitHub repository | Existing or new private/public repo as appropriate | Source handoff |
| P0 | Hosting account | Static frontend and Django API runtime | Assessment hosted app |

## Recommended during implementation or production hardening

| Priority | Service/tool | Needed when |
|---|---|---|
| P1 | Docker Desktop / compatible Docker engine | Reproducible local DB/queue services |
| P1 | PostgreSQL | Durable plan/job/result storage |
| P1 | Redis | Cache, throttling state and Celery broker |
| P1 | Worker hosting | Provider fanout exceeds API timeout budget |
| P1 | GitHub Actions or existing CI | Repeatable tests/build/deploy |
| P1 | Managed secrets manager | Real hosted environment |
| P1 | Error monitoring | Production reliability and triage |
| P2 | OpenTelemetry/Prometheus dashboard | Verified high-traffic needs |
| P2 | CDN/WAF | Public access abuse/cost concerns |

## Provider-specific cautions

- HERE's truck routing may require proper vehicle dimensions/weight for real road restrictions. The assignment only asks for **load weight for weather overrides**; do not invent gross vehicle weight or dimensions.
- `alternatives=2` requests two alternatives in addition to main route; not a promise of 3 real options.
- Open-Meteo **free API is non-commercial** and rate-limited. Use paid/approved licensing for commercial hosted usage; confirm terms and data attribution.
- MapLibre GL JS does not serve maps. A separate tile/style provider and its license/attribution are required; demo tiles are unsuitable for real traffic.
- Weather provider is authoritative only for modeled forecast variables; it does not certify real truck safety.

## Environment variable names to preload

See the copyable `.env.example` in repo root. Important: `DATA_MODE`, `HERE_API_KEY`, `HERE_ROUTING_BASE_URL`, `HERE_GEOCODING_BASE_URL`, `OPEN_METEO_BASE_URL`, `OPEN_METEO_API_KEY` (if required), `VITE_MAP_STYLE_URL`, `DATABASE_URL`, `REDIS_URL`, `DJANGO_SECRET_KEY`, `FRONTEND_ORIGIN`, `ALLOWED_HOSTS`, `PLANNING_CONCURRENCY`, provider timeouts, policy/scoring settings, cache TTL and guest retention.

## Before asking an agent to start

1. Choose prototype/noncommercial or paid production weather use.
2. Activate HERE routing + geocoding and verify an example truck route in official API console.
3. Select a lawful map tile/style; open it in a browser and verify attribution.
4. Create `.env` locally from `.env.example`, fill secrets locally, ensure `.gitignore` covers it.
5. Connect GitHub, set up deploy account later; no need to buy Kubernetes or microservices.
6. Paste `docs/15_AI_EXECUTION_PROMPT.md` into your coding assistant and grant repo edit/run tools as appropriate.
