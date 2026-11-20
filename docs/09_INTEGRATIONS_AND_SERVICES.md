# 09 — Provider integration, technology and licensing plan

**Verified source pages (checked 20 Nov 2026; recheck before production):**

- HERE truck routing: https://docs.here.com/routing/docs/routing-v8-truck-routing
- HERE v8 route API reference: https://docs.here.com/routing/reference/routing-api-v8-calculateroutes
- Open-Meteo Weather Forecast API: https://open-meteo.com/en/docs
- Open-Meteo pricing/licensing: https://open-meteo.com/en/pricing
- MapLibre GL JS heatmap: https://maplibre.org/maplibre-gl-js/docs/examples/create-a-heatmap-layer/

## Provider decisions

| Capability | Recommended option | Required? | Setup |
|---|---|---|---|
| Truck-aware routing and alternatives | HERE Routing API v8 `transportMode=truck`, `alternatives=2` | **Yes** | HERE developer project + key + route quota |
| Geocoding/place suggestions | HERE Geocoding & Search or reusable provider already integrated | **Yes** if text entry | Enable API and test locale/disambiguation |
| Hourly checkpoint weather | Open-Meteo forecast (or licensed equivalent) | **Yes** | Verify variables, units, horizon, source/licensing |
| Basemap/tiles/style | Licensed compatible map style and tile service | **Yes** | Obtain style URL/token and verify attribution/traffic |
| Map and heatmap renderer | MapLibre GL JS | **Yes** (recommended library) | npm dependency; not an API key by itself |
| PostgreSQL | Managed or Docker local | Recommended | DB credentials; private network |
| Redis | Managed or Docker local | Recommended for load/queue | Redis connection URL |
| Celery worker | Python service, Redis broker | If request work exceeds HTTP budget | Worker process/queues |
| Deploy | Static frontend + Python API/worker + DB/Redis | For hosted deliverable | Hosting account, domain/HTTPS, secrets |
| Sentry/OpenTelemetry | Optional monitoring | Production hardening | Token/project if chosen |

## HERE specifics

- Route request: origin, destination, `transportMode=truck`, desired alternatives, departure and applicable vehicle configuration. HERE's documented `alternatives` is the number of alternative routes **in addition to** optimal. Requesting `alternatives=2` targets 3 total, but none or fewer may be returned. Do not invent them.
- Optional actual truck dimensions/axles/gross mass should only be sent if collected or reliably derived. The assignment supplies **load weight** for weather-risk overrides, not full truck profile. Do **not** misrepresent cargo weight as total gross vehicle weight for road restriction calculations.
- Preserve truck-route warnings and violations. Geocode beforehand; store location label and coordinate. Compare provider geometry/version and dedupe close duplicates conservatively.
- Route use and display might be subject to provider terms; check whether selected tile/style service and HERE response usage are contractually compatible before production.

## Weather provider details

Open-Meteo documents hourly variables including `wind_speed_10m`, `rain`, `snowfall`, and explicit output units. Use response-provided `hourly_units`, validate values and time grids, and normalize server-side. Hourly forecasts are modeled estimates, not real-time road observations. Sampling may require a multi-coordinate query or bounded batches. Verify supported batching, max request size, model horizon and current quotas before optimizing.

**Licensing:** Open-Meteo free tier is **non-commercial**, has request limits and no uptime guarantee; commercial deployment requires an appropriate plan/contract. The plan's weather-data attribution obligations should be reviewed. Do not promise free commercial usage.

## Tile and map details

MapLibre is a client renderer, **not** a hosted tile service. Supply a permitted map style and tile server separately; do not use MapLibre's demonstration tiles for production traffic. Map style, tile API token, attribution and usage limits belong in configuration. Use native GeoJSON line/circle/heatmap layers, not hundreds of React DOM markers for dense corridors.

## Provider interface and failover

Wrap adapters behind stable ports. Normalize all provider formats into internal DTOs. On 429/5xx: bounded retry with backoff, cache where legally permitted, circuit-break after recurrent failures, never downgrade to made-up weather. Multiple weather providers are optional: do not aggregate inconsistent models silently; if fallback happens, label source and apply same normalizer/quality checks.

## Owner onboarding order

1. HERE project and routing key.
2. Weather provider mode confirmed: prototype vs commercial, with approved endpoint/plan.
3. Licensed basemap/style and tile API token if required.
4. Optional HERE geocoding access if separate entitlement.
5. Hosting, Postgres, Redis (can be local Docker initially).
6. CI secrets and monitoring optional, after functional baseline.

See `docs/22_SERVICE_SETUP_CHECKLIST.md` for exact variable names and verification steps.
