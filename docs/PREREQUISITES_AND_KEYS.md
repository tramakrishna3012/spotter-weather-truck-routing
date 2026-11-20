# Prerequisites, Accounts, API Keys & Procurement Guide

This guide is the owner's actionable checklist for moving **Spotter (Weather-Aware Truck Routing)** from local deterministic `fixture` mode to **live API mode** and **hosted production**.

> **CRITICAL SECURITY RULE**
> - **NEVER** paste real API keys, tokens, database passwords, or `DJANGO_SECRET_KEY` values into AI chat prompts, GitHub issues, pull requests, screenshots, or committed files.
> - Store secrets **only** in your local gitignored `.env` file (for local testing) or in your hosting provider's encrypted secrets manager (for staging/production).
> - Never place private server keys (`HERE_API_KEY`, `OPEN_METEO_API_KEY`, `DJANGO_SECRET_KEY`, `DATABASE_URL`, `REDIS_URL`) into `VITE_*` variables — Vite bundles `VITE_*` values directly into public client JavaScript.

---

## Quick Decision Matrix

| Priority | Item | Needed in `fixture` mode? | Needed in `live` mode? | Needed in `production`? |
|---|---|---:|---:|---:|
| **P0** | HERE Routing API v8 + Geocoding & Search API Key | No | **Yes** | **Yes** |
| **P0** | Open-Meteo Endpoint (+ API Key if commercial) | No | **Yes** | **Yes** (Commercial plan) |
| **P0** | Licensed MapLibre Basemap Style URL (+ optional public domain-restricted token) | No (fallback) | **Recommended** | **Yes** (Never demo tiles) |
| **P0** | Production `DJANGO_SECRET_KEY` | No (dev fallback) | Recommended | **Yes** |
| **P0** | Hosting Platforms (Static SPA + Django API + Postgres + Redis) | No | Local optional | **Yes** |
| **P1** | Managed PostgreSQL (`DATABASE_URL`) | No (SQLite) | Optional | **Yes** |
| **P1** | Managed Redis (`REDIS_URL`) | No | Optional | **Recommended** (Required for async) |
| **P1** | Celery Async Worker (`ENABLE_ASYNC_PLANNING=true`) | No | No | Only when latency/load warrants |
| **P1** | Error Monitoring (Sentry) & Metrics (Prometheus) | No | No | **Recommended** |
| **P1** | GitHub Actions Deployment Secrets | No | No | When automating CD |
| **N/A** | OAuth/SSO, Billing, Kubernetes, Kafka | **Not needed for MVP** | **Not needed for MVP** | **Not needed for MVP** |

---

## P0 — Required for Live Mode & Hosted Deployment

### 1. HERE Routing API v8 + HERE Geocoding & Search API (`HERE_API_KEY`)

Spotter uses HERE server-side for **truck-aware routing with alternatives** (`transportMode=truck`, `alternatives=2`) and **location autocomplete / geocoding**.

- **Sign-up & Console:** [https://platform.here.com/](https://platform.here.com/)
- **API Documentation:**
  - Truck Routing v8: [https://docs.here.com/routing/docs/routing-v8-truck-routing](https://docs.here.com/routing/docs/routing-v8-truck-routing)
  - Calculate Routes Reference: [https://docs.here.com/routing/reference/routing-api-v8-calculateroutes](https://docs.here.com/routing/reference/routing-api-v8-calculateroutes)
  - Geocoding & Search v1: [https://docs.here.com/geocoding-search-api/dev_guide/index.html](https://docs.here.com/geocoding-search-api/dev_guide/index.html)

**Step-by-step console setup:**
1. Sign up for a HERE Platform account (Base Plan includes a monthly free transaction tier suitable for development/evaluation; confirm current quota and overage billing limits in your billing dashboard).
2. Open **Access Manager -> Projects** and click **Create new project** (e.g., `spotter-truck-routing`).
3. Ensure the project includes access to **HERE Routing API v8** and **HERE Geocoding & Search API v1** (included under standard Location Services resources).
4. Inside the project, go to **Apps -> Register new app** (e.g., `spotter-backend-api`).
5. Under the app's **Credentials** tab, select **API Keys** and click **Create API key**.
6. Copy the generated key immediately into your local `.env` as `HERE_API_KEY=` (server-side only).
7. Set a billing alert / monthly quota cap in the HERE Billing portal to guard against runaway traffic.

**Important HERE caveats:**
- **Payload weight vs. gross vehicle weight:** The assessment input is *cargo payload weight* used for wind/weather override rules. Do **not** misrepresent payload weight as total gross vehicle weight (`grossWeight`) or fabricate truck dimensions/axles when calling HERE truck restrictions.
- **Alternative routes:** `alternatives=2` requests up to 2 alternatives *in addition to* the primary route (up to 3 total), but HERE may legitimately return 0, 1, or 2 routes depending on corridor geography.
- **Data display terms:** Review HERE's license terms regarding displaying HERE route geometries on third-party map tiles before commercial launch.

---

### 2. Open-Meteo Hourly Forecast API (`OPEN_METEO_BASE_URL`, `OPEN_METEO_API_KEY`)

Spotter queries Open-Meteo server-side for hourly `wind_speed_10m`, `rain`, and `snowfall` forecasts along internal route scoring checkpoints and for the 0–48h exploratory corridor heatmap.

- **Docs:** [https://open-meteo.com/en/docs](https://open-meteo.com/en/docs)
- **Pricing & Commercial Licensing:** [https://open-meteo.com/en/pricing](https://open-meteo.com/en/pricing)

**CRITICAL LICENSING SPLIT — Decide before going live:**

| Use Case | Base URL (`OPEN_METEO_BASE_URL`) | API Key (`OPEN_METEO_API_KEY`) | Terms & Caveats |
|---|---|---|---|
| **Non-commercial / Interview / Prototype Evaluation ONLY** | `https://api.open-meteo.com/v1` | *(leave blank)* | **Strictly non-commercial** (CC BY 4.0 attribution required). Shared rate limits, no SLA or uptime guarantee. **Never use for commercial SaaS or customer-facing commercial dispatch.** |
| **Commercial / Paid Production Deployment** | `https://customer-api.open-meteo.com/v1` | **Required** (paid key) | Dedicated commercial endpoint, higher rate limits, commercial license rights, SLA options. |

**Step-by-step setup (if commercial):**
1. Visit [https://open-meteo.com/en/pricing](https://open-meteo.com/en/pricing) and select a commercial tier sized to your expected monthly API call volume (account for batched checkpoint queries + 0–48h heatmap fetches, mitigated by `WEATHER_CACHE_TTL_SECONDS=900`).
2. After subscribing, open the Open-Meteo Customer Portal and generate an API key.
3. Set `OPEN_METEO_BASE_URL=https://customer-api.open-meteo.com/v1` and `OPEN_METEO_API_KEY=<your-key>` in your `.env` / production secret manager.
4. Keep Open-Meteo weather data attribution visible in the application UI as required by your plan.

---

### 3. Licensed MapLibre Basemap Style & Tiles (`VITE_MAP_STYLE_URL`, `VITE_MAP_PUBLIC_TOKEN`)

**CRITICAL CAVEAT:** **MapLibre GL JS is only an open-source client-side rendering library — it does NOT host production map tiles.** MapLibre's demo style (`https://demotiles.maplibre.org/style.json`) is strictly for tiny library demos and **must never be used for live traffic or production deployments**.

You must provision a separately licensed vector/raster tile provider that is compatible with your commercial usage and routing provider terms:

| Provider Option | Sign-up URL | Notes & Licensing |
|---|---|---|
| **MapTiler Cloud** *(easiest setup)* | [https://cloud.maptiler.com/](https://cloud.maptiler.com/) | Free dev tier (non-commercial / low volume); paid Flex/Pro plans for commercial apps. Generates a ready-to-use `style.json` URL. Supports HTTP Referer domain restrictions. |
| **Stadia Maps** | [https://stadiamaps.com/](https://stadiamaps.com/) | Clean MapLibre vector styles (Alidade Smooth / OSM Bright). Free local dev, commercial plans with domain allowlisting. |
| **Protomaps / Self-Hosted PMTiles** | [https://protomaps.com/](https://protomaps.com/) | Host OSM-derived PMTiles on your own S3/Cloudflare R2 bucket for predictable zero-per-tile-fee scaling (requires OSM attribution). |
| **HERE Vector Tile API / AWS Location Service** | [https://platform.here.com/](https://platform.here.com/) / [https://aws.amazon.com/location/](https://aws.amazon.com/location/) | Strong choice if you want basemap tiles and truck routing under the same commercial provider agreement (HERE). |

**Step-by-step console setup (example: MapTiler Cloud / Stadia Maps):**
1. Create an account at your chosen tile provider and choose an appropriate free-dev or commercial plan.
2. Select a high-contrast, uncluttered road/navigation vector style (dark or neutral light style so risk-colored route overlays remain legible).
3. Create a **browser/public API key** and **restrict it by allowed HTTP Referer / Origin domains** (e.g., `http://localhost:5173/*`, `http://localhost:8080/*`, `https://your-production-domain.com/*`).
4. Copy the provider's style JSON URL into `VITE_MAP_STYLE_URL` (and if your provider separates the token from the style URL, place the domain-restricted public token in `VITE_MAP_PUBLIC_TOKEN`).
5. Verify in the browser that tiles load without `403` errors and that the provider's required map attribution (`© OpenStreetMap contributors`, provider mark) renders cleanly in the map footer.

---

### 4. Production `DJANGO_SECRET_KEY`

Django uses `DJANGO_SECRET_KEY` to sign guest session cookies, CSRF tokens, and cryptographic signatures. Startup validation rejects weak/empty keys in production.

**Generate a secure key locally (never reuse dev placeholders):**
```bash
python3 -c 'import secrets; print(secrets.token_urlsafe(50))'
```
- Paste the output directly into your production secret manager as `DJANGO_SECRET_KEY`.
- If a key is ever accidentally exposed, generate a new key immediately and redeploy (note: rotating invalidates active guest sessions, which is low-impact for ephemeral guest plans).

---

### 5. Hosting Platforms (Static SPA + Django API + Postgres + Redis)

Spotter follows a clean **modular monolith** topology (`docs/02_ARCHITECTURE.md`):

| Component | Recommended Hosting Options | Key Configuration Requirements |
|---|---|---|
| **Frontend Static SPA** (`frontend/dist`) | Cloudflare Pages, Vercel, Netlify, or AWS S3 + CloudFront | Build command: `npm ci && npm run build`; output dir: `dist`; set `VITE_API_BASE_URL`, `VITE_MAP_STYLE_URL`, `VITE_MAP_PUBLIC_TOKEN`; enforce HTTPS; configure SPA fallback to `index.html`. |
| **Backend Django API** (`backend/`) | Render Web Service, Railway, Fly.io, or AWS ECS Fargate | Run migrations on release (`python manage.py migrate --noinput`); serve with Gunicorn (`config.wsgi:application`); set `APP_ENV=production`, `DJANGO_DEBUG=false`, `SESSION_COOKIE_SECURE=true`, exact `ALLOWED_HOSTS`, `FRONTEND_ORIGIN`, and `DJANGO_CORS_ALLOWED_ORIGINS`; health check path `/api/v1/health/live` and readiness `/api/v1/health/ready`. |
| **PostgreSQL & Redis** | Managed add-ons on Render / Railway / Supabase / Neon / Upstash / AWS RDS + ElastiCache | Private network or TLS (`sslmode=require`, `rediss://`); least-privilege non-superuser DB credentials. |

---

## P1 — Recommended for Production Scale & Hardening

### 1. Managed PostgreSQL (`DATABASE_URL`)
- **Why:** Durable storage for trip plans, idempotency keys, async job state, and audit metadata across multiple API replicas (replaces local SQLite).
- **Format:** `postgres://<db_user>:<db_password>@<db_host>:5432/<db_name>?sslmode=require`
- **Hardening:** Create a dedicated application role without `SUPERUSER` privileges, enable automated daily backups, and test a restore before claiming DR readiness.

### 2. Managed Redis (`REDIS_URL`)
- **Why:** Shared weather & route response caching (reduces HERE/Open-Meteo spend and latency), distributed per-scope rate limiting, request coalescing, and Celery task broker.
- **Format:** `rediss://:<redis_password>@<redis_host>:6379/0` (use `rediss://` TLS in production).

### 3. Celery Worker Service (`ENABLE_ASYNC_PLANNING=true`)
- **When to enable:** Only once measured live request latency (p95/p99) or long-corridor weather fanout approaches your HTTP timeout budget (see `ADR-015` in `docs/16_DECISIONS_AND_OPEN_QUESTIONS.md`).
- **How to run:**
  - Locally via Docker Compose: `COMPOSE_PROFILES=async docker compose up --build`
  - In production: Deploy a separate worker service using the same `backend` Docker image with command `celery -A config worker -l info --concurrency=${PLANNING_CONCURRENCY:-4}`, setting `ENABLE_ASYNC_PLANNING=true` on both API and worker services.

### 4. Observability — Sentry & Prometheus
- **Error Tracking (Sentry):** Create a project at [https://sentry.io/](https://sentry.io/) if desired; store `SENTRY_DSN` in your secret manager and ensure before-send hooks scrub exact trip coordinates, origin/destination strings, and authorization headers (per `docs/10_SECURITY.md` and `docs/18_OBSERVABILITY.md`).
- **Metrics (Prometheus):** Scrape Django/worker metrics internally (never expose unauthenticated metrics publicly on the open internet) and avoid high-cardinality labels like `plan_id`.

### 5. GitHub Actions Deployment & CI Secrets
- Current CI (`.github/workflows/ci.yml`) runs completely in deterministic `fixture` mode and requires **zero external API keys**.
- When adding automated staging/production deployments later, configure secrets under **GitHub Repository -> Settings -> Secrets and variables -> Actions** (scoped to `staging` and `production` GitHub Environments with required reviewers):
  - Hosting deploy tokens (e.g., Render/Fly/Cloudflare API token)
  - Optional live-smoke-test credentials (strictly quota-capped, never run on untrusted fork PRs)

---

## Explicitly Not Needed for MVP

Do **not** spend time or budget provisioning these before product demand justifies them:

- **OAuth / SSO / User Accounts / Multi-Tenant RBAC:** Assessment and MVP use ephemeral scoped guest sessions (`ADR-011`).
- **Billing / Subscriptions (Stripe, etc.):** Not part of the routing/risk assessment scope.
- **Kubernetes / Service Mesh / Microservices Split:** Modular monolith (`ADR-001`) scales cleanly on managed containers/PaaS without K8s operational overhead.
- **Kafka / Event Streaming / Data Warehouse:** Standard PostgreSQL + Redis/Celery covers all planning and audit workflows.
- **Self-Hosted Routing Engine (OSRM/Valhalla) or Raw NWP Weather Ingestion (GFS/HRRR GRIB):** HERE Truck Routing v8 and Open-Meteo provide authoritative, maintained APIs.

---

## Copy-Pasteable `.env` Snippet for Local Live Mode

1. Copy the template:
   ```bash
   cp .env.example .env
   ```
2. Edit your **local-only** `.env` file (never commit it; `.gitignore` blocks it and CI enforces this) and replace the `<PLACEHOLDER>` values:

```dotenv
# --- Core Runtime (Local Live Mode) ---
APP_ENV=development
DATA_MODE=live
DJANGO_DEBUG=true
DJANGO_SECRET_KEY=<PASTE_50_PLUS_CHAR_RANDOM_SECRET_FROM_PYTHON_SECRETS>
FRONTEND_ORIGIN=http://localhost:5173
ALLOWED_HOSTS=localhost,127.0.0.1
DJANGO_CORS_ALLOWED_ORIGINS=http://localhost:5173
SESSION_COOKIE_SECURE=false

# --- Frontend Build / Dev Public Settings ---
VITE_API_BASE_URL=http://localhost:8000
VITE_MAP_STYLE_URL=<PASTE_LICENSED_STYLE_JSON_URL_FROM_MAPTILER_OR_STADIA>
VITE_MAP_PUBLIC_TOKEN=<OPTIONAL_DOMAIN_RESTRICTED_PUBLIC_TILE_TOKEN>

# --- HERE Routing & Geocoding (Server-Side Only) ---
HERE_API_KEY=<PASTE_HERE_PLATFORM_API_KEY>
HERE_ROUTING_BASE_URL=https://router.hereapi.com/v8
HERE_GEOCODING_BASE_URL=https://geocode.search.hereapi.com/v1

# --- Open-Meteo Weather (Server-Side Only) ---
# Prototype / non-commercial evaluation:
OPEN_METEO_BASE_URL=https://api.open-meteo.com/v1
OPEN_METEO_API_KEY=
# Commercial production (uncomment & replace above):
# OPEN_METEO_BASE_URL=https://customer-api.open-meteo.com/v1
# OPEN_METEO_API_KEY=<PASTE_OPEN_METEO_COMMERCIAL_API_KEY>

# --- Optional Local Docker Postgres/Redis & Async Mode ---
DATABASE_URL=postgres://spotter:spotter_local_dev@localhost:5432/spotter
REDIS_URL=redis://localhost:6379/0
ENABLE_ASYNC_PLANNING=false
PLANNING_CONCURRENCY=4
```

---

## Owner Pre-Flight Verification Checklist

Before running live mode or deploying to production, verify each step locally:

1. **Git hygiene:** Run `git status` and confirm `.env` does **not** appear as untracked or staged.
2. **HERE key works:** Test your `HERE_API_KEY` in the HERE API console or via a local curl (without printing the key into shared logs) for a truck route (`transportMode=truck&alternatives=2`) and a geocode query.
3. **Weather licensing confirmed:** Verify whether your deployment is non-commercial evaluation (`api.open-meteo.com`) or commercial (`customer-api.open-meteo.com` + paid key).
4. **Basemap loads with attribution:** Open your `VITE_MAP_STYLE_URL` in the running frontend, verify no console `401`/`403` tile errors, and confirm required provider/OSM attribution is visible.
5. **Health endpoints green:** Start the stack (`make dev-backend` / `make dev-frontend` or `make docker-up`) and confirm:
   - `GET http://localhost:8000/api/v1/health/live` returns `200 OK`
   - `GET http://localhost:8000/api/v1/health/ready` returns `200 OK`
6. **Production guardrails enabled:** Before deploying publicly, verify `APP_ENV=production`, `DJANGO_DEBUG=false`, `SESSION_COOKIE_SECURE=true`, strict `ALLOWED_HOSTS`/`DJANGO_CORS_ALLOWED_ORIGINS`, HTTPS enabled, and non-empty `DJANGO_SECRET_KEY`.
