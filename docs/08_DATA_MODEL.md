# 08 — Data storage, caching, TTL and privacy

Store only what the working product needs. Avoid a fleet-grade schema before the assessment calls for it. Example entities below are proposals for PostgreSQL; JSONB/normalized routes are both acceptable with evidence.

## Core entities

| Entity | Main fields | Constraints |
|---|---|---|
| `Plan` | opaque ID, owner/session scope, origin/destination (sensitive), departure UTC, load lb, display spacing, created/expires UTC, status, policy version | owner-scoped, TTL, indexed status/created |
| `RouteCandidate` | plan FK, provider route ID, geometry/geometry ref, distance m, duration sec, provider warnings, validity flag | unique per plan + provider fingerprint |
| `Checkpoint` | route FK, index, cumulative distance m, coordinate, ETA UTC, provider forecast time, risk/status | ordered unique route + index |
| `WeatherObservation` | provider/source, coordinate key, valid UTC, issued UTC, normalized units, quality/coverage | short TTL; may live only in Redis |
| `RouteRiskSummary` | route FK, risk miles by level, weighted average, unknown miles, eligible flag, reasons | deterministic policy version |
| `PlanJob` | plan FK, status, attempts, idempotency key, created/started/completed, error code | attempts bounded, ensure idempotency |
| `ForecastSliceCache` | plan/ref, selected valid-at, risk layer payload, coverage, source time | renewable TTL and partition by time |

Do not persist provider raw location traces longer than necessary. Prefer storing the smallest representation that supports review and map playback. If long-term trip persistence is unnecessary, short-lived results in a scoped cache are enough, with PostgreSQL for job state only.

## Cache keys

Use structured hashing of provider, geographic precision policy, transport mode and truck constraints, start/end coordinates, provider-specific options, departure time bucket, forecast issuance/model, policy version and serialization version. **Do not** accidentally reuse a route result across different truck parameters or different forecast valid-time slices. TTLs configured in seconds from environment validated config.

## Retention and deletion

Use named runtime config for plan retention, weather freshness, job retention and log retention; do not hardcode durations throughout code. Delete guest session results at expiry; ensure cache invalidation and job cancellation don't expose stale data. Production privacy policy should explain storage and data processors.

## Index and query design

- `Plan(id, expires_at, owner_scope)` indexed for scoped fetch.
- `PlanJob(status, created_at)` for queue supervision.
- `Checkpoint(route_id, checkpoint_index)` for deterministic ordering.
- Fetch a complete plan with bounded prefetch/joins to avoid N+1 queries.
- Only add PostGIS if actual spatial SQL queries warrant it; the core route polyline can remain GeoJSON from provider.

## Multi-user isolation

Use an authentication identity *or* signed/opaque scoped guest token. Even in guest MVP, a plan ID alone must not grant public read access unless this is a documented user-approved sharing behavior. Rate-limit by IP and scoped identity; never trust arbitrary client-provided `owner_id`. Employ database row-level tenant isolation only if actual multi-tenant user accounts enter scope.

## Recovery

Durable jobs must be retry-safe: deduplicate submissions, transition statuses atomically, record attempt count, use bounded retry with jitter, and avoid double-charging provider quotas when possible. If worker dies, a lease/timeout recovers the job; a recovered job never overwrites a newer completed result without version validation.
