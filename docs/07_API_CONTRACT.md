# 07 — Proposed REST and event contracts

**Status:** proposed. Reconcile with existing code; use versioned DRF endpoints and generated OpenAPI/typed TypeScript contracts. Only backend can generate recommendation and risk classifications.

## `POST /api/v1/plans`

Headers: `Content-Type: application/json`, optional `Idempotency-Key: <opaque-uuid>`; authentication/session header as required by the chosen access model.

```json
{
  "origin": {"latitude": 40.7128, "longitude": -74.0060, "label": "New York, NY"},
  "destination": {"latitude": 39.9526, "longitude": -75.1636, "label": "Philadelphia, PA"},
  "departure_at": "2026-11-20T09:00:00-05:00",
  "load_weight_lb": 32000,
  "display_checkpoint_miles": 25
}
```

The coordinates, date and weight above are **example schema values only**, not recommended default trip values. Do not preload them as real user results. Server validates coordinate range, recognized locations, timezone offset, configured horizon, finite nonnegative load and supported spacing. Expose immutable `policy_version`. If request is expensive, return `202 Accepted`:

```json
{
  "plan_id": "opaque-id",
  "state": "queued",
  "poll_after_seconds": 2,
  "status_url": "/api/v1/plans/opaque-id"
}
```

If performing a successful synchronous plan, returning `200` with result contract is acceptable. Make the request path consistent and documented; do not sometimes return fake success.

## `GET /api/v1/plans/{plan_id}`

**Pending:** `state` is one of `queued`, `routing`, `sampling_weather`, `scoring`; include bounded progress stage, timestamps and retry guidance. **Completed response:**

```json
{
  "plan_id": "opaque-id",
  "state": "completed",
  "generated_at": "2026-11-20T12:10:00Z",
  "data_mode": "live",
  "policy_version": "risk-policy-v1",
  "recommendation_status": "recommended",
  "recommended_route_id": "route-a",
  "recommendation_reason": "Lowest Severe miles among covered eligible routes",
  "routes": [
    {
      "id": "route-a",
      "geometry": {"type":"LineString","coordinates":[[-74.006,40.7128],[-75.1636,39.9526]]},
      "distance_m": 160000,
      "duration_seconds": 8400,
      "risk": {
        "severe_miles": 0.0,
        "high_miles": 4.2,
        "no_travel_miles": 0.0,
        "unknown_miles": 0.0,
        "weighted_average_risk": 0.46,
        "eligible": true,
        "coverage_fraction": 1.0
      },
      "checkpoints": [],
      "risk_segments": [],
      "eta_method": "provider_timing",
      "provider_warnings": []
    }
  ],
  "forecast": {
    "issued_at": "2026-11-20T10:00:00Z",
    "valid_until": "2026-11-22T10:00:00Z",
    "timezone": "UTC",
    "coverage_complete": true
  },
  "warnings": []
}
```

**IMPORTANT:** Example numbers and geometry above are deliberately schematic. In implementation, result data must come from real provider and engine outputs; example payload must not become production fixture automatically.

### Subobjects

`checkpoint` should include `{id, cumulative_distance_m, lat, lon, eta_at, weather_valid_at, wind_mph, rain_in_per_hr, snow_in_per_hr, risk_severity, risk_reasons, weather_status, forecast_issued_at}`.

`risk_segment` should include `{from_distance_m, to_distance_m, severity, status, reason_codes}`. `status` can be `known`, `unknown`, `no_travel`. All visual map segment values MUST be backend-created, not calculated from colors.

`forecast slice` should include `{hour_offset, valid_at, cells/points, coverage_fraction, data_origin}` and match the heatmap source schema; app can fetch a selected slice separately to reduce initial payload.

## `GET /api/v1/plans/{plan_id}/forecast?hour_offset={0..48}`

Return only selected corridor heatmap data with a stable `valid_at` (UTC), source coverage and severity/variable values, or an honest unavailable state. This is **wall-clock offset from the chosen forecast reference**. Clearly define the reference in metadata (e.g. departure instant or forecast snapshot instant), and use the same reference for every slider tick. Handle forecast beyond provider horizon by `422 forecast_out_of_range` or a `coverage_complete=false` response, never placeholders.

## Error envelope

```json
{
  "error": {
    "code": "WEATHER_COVERAGE_INCOMPLETE",
    "message": "Weather coverage is unavailable for part of this trip.",
    "retryable": true,
    "request_id": "opaque-trace-id",
    "details": []
  }
}
```

HTTP: `400` malformed, `422` domain validation, `401/403` scoped access, `404` unknown/hidden ID, `409` duplicate conflict, `429` limited requests, `502/503` provider unavailability, `504` provider/worker timeout. When a partially computed trip has unknown coverage, prefer a completed **non-recommended** result rather than a fabricated `200` recommended route.

## Access and lifecycle

- `GET /api/v1/health/live`: process alive only; no secrets.
- `GET /api/v1/health/ready`: required dependencies healthy; limited diagnostic exposure.
- `DELETE /api/v1/plans/{id}`: optional privacy cleanup, ownership scoped.
- `POST /api/v1/plans/{id}/cancel`: optional idempotent cancellation if queued; do not claim it stops an already running provider request unless cancellation is implemented.
- Short, opaque IDs; TTL from config; scoped access by authenticated owner or signed anonymous access token. Do not store precise route data in browser analytics.

## Versioning and contracts

Generate OpenAPI from DRF and use CI to detect schema breaking changes. Preserve backend policy version with results. Add consumer tests for error, partial, no-route, all-blocked, unavailable data, invalid provider payload and canceled job.
