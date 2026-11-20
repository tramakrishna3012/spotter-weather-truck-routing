# 06 — Weather risk engine: executable policy specification

**Risk is safety-sensitive.** Source: `reference/fs-assessment-spotter.pdf` pages 1–2. This document resolves algorithmic ambiguity for implementation and requires exhaustive tests. Report uncertainties; do not exaggerate actual safety assurance.

## Units and source variables

**Canonical units:** wind `mph`, rain `in/hr`, snowfall `in/hr`, load `lb`, distance `m` (convert to mi for reported assessment mileage), timestamps UTC. For Open-Meteo, fetch hourly `wind_speed_10m`, `rain`, `snowfall` and applicable time indices, verify each response's `hourly_units` (commonly km/h and mm for wind/rain, cm for snowfall), and convert using explicit unit-aware helper functions; **do not assume all precipitation is rain**. `snowfall` in centimeters per sampling hour must be converted to inches/hour using 2.54 cm per inch. Rain in mm/hour uses 25.4 mm/in. Wind km/h uses 1.609344 km/mi. Validate actual provider metadata before conversion.

## Exact threshold rule table

| Metric | Low | Moderate | High | Severe | No Travel |
|---|---|---|---|---|---|
| Wind (mph) | `<25` | `>=25,<35` | `>=35,<45` | `>=45,<55` | `>=55` |
| Rain (in/hr) | `<0.10` | `>=0.10,<0.25` | `>=0.25,<0.50` | `>=0.50,<=1.00` | `>1.00` |
| Snow (in/hr) | `<0.5` | `>=0.5,<1.0` | `>=1.0,<2.0` | `>=2.0,<=3.0` | `>3.0` |

These **half-open interpretations** resolve the overlapping endpoints in the PDF and preserve the strict source `>1.00` and `>3.0` No Travel thresholds. Introduce a versioned `RiskPolicy` constant/configuration model and test exact thresholds using decimal-safe values or precise comparison. Reject negative/nonfinite measurements as invalid, not Low.

### Wind + payload overrides

1. Wind >= 55 mph => No Travel **for any weight**.
2. 45 <= wind < 55 mph AND load > 30000 lb => No Travel.
3. 35 <= wind < 45 mph AND load > 40000 lb => Severe.
4. Otherwise preserve base wind severity. `load == 30000` or `==40000` does not trigger strict-greater override.
5. Combined checkpoint severity is the **maximum** of wind, rain and snow after overrides; report every contributing hazard and override reason.

Enum order `LOW=0`, `MODERATE=1`, `HIGH=2`, `SEVERE=3`, `NO_TRAVEL=4`, plus separate `UNKNOWN` (not rank 0). Policy values are specified by the assignment and must not be tuned by an AI to produce prettier results.

## Checkpoint generation and ETA

- Validate route geometry and per-section distance/time; reject zero/negative/invalid total length.
- Create internal conservative scoring checkpoints at `0, spacing, 2*spacing ... total` using distance along route, including **both endpoints** exactly once. Use an internal default no coarser than 10 miles unless route-provider and forecast coverage limits are evaluated and an ADR is recorded.
- UI separately permits 10, 25 or 50 mile **display** checkpoints. User choice must not change ranking. A 50-mile display can hide markers, never hazards.
- Prefer provider cumulative travel times along the route; calculate ETA from departure + cumulative time. If only total route duration is available, approximate ETA proportionally by distance and mark `eta_method=proportional_approximation`; no fake precision.
- Weather data must correspond to checkpoint ETA and be within provider horizon. For conservative classification between hourly forecast bins, consider both neighboring hourly values and use the worse category for **safety classification** (or use an equally conservative documented approach). Temporal interpolation may be used for visual readings but must never erase an observed higher-risk adjacent hour.
- At route endpoint and at short final interval, length-weight risk contributions accurately. Attribute each route segment to the nearest checkpoint on distance axis with Voronoi/midpoint boundaries, or use a strictly documented equivalent; ensure all nonzero route miles are accounted for exactly once.

## Computation pseudocode

```text
validate(request)
route_candidates = routing_port.alternatives(request)
valid_unique_routes = validate_and_deduplicate(route_candidates)
for route in valid_unique_routes:
    score_points = sample_distance(route, configured_internal_spacing)
    timestamps = estimate_checkpoint_ETAs(route, score_points, departure_utc)
    forecasts = weather_port.batch(points, timestamps, provider_horizon)
    classifications = classify_or_unknown(forecasts, load_lb, risk_policy)
    segment_miles = assign_distance_weighted_miles(classifications, route.length_m)
    score = {
        severe_miles, high_miles, weighted_average_risk,
        no_travel_miles, unknown_miles, duration_seconds
    }
    eligible = (no_travel_miles == 0 AND unknown_miles == 0 AND required_checks_pass)
    record score, coverage, policy_version, forecast_issued_at, reasons
eligible = filter(all_routes, eligible)
recommended = min(eligible, key=(severe_miles, high_miles, avg_risk, duration_sec, deterministic_route_id)) if eligible else None
```

Average risk is **distance-weighted** across known segments using ordinal risk values 0–3; No Travel is an eligibility gate, not averaged away. Ranking uses **lexicographic comparison**, not a combined arbitrary risk coefficient. Distances may be in meters internally but must use consistent conversion for ranking/display.

## Important semantics

- If a route contains **any** No Travel segment, it is ineligible for recommendation. Still render it with explicit risks.
- If required weather is missing, coverage is `unknown`, making it ineligible for recommendation (until fresh data arrives). Never fill null with zero.
- If no routes eligible, return `recommended_route_id=null` and `recommendation_status=no_eligible_route` or `insufficient_weather_data` with reasons.
- Forecast corridor slider shows weather **at selected wall-clock time** and not necessarily at the truck's predicted ETA. Label separately. If coverage is poor, show gaps rather than smearing heat across unsampled regions.
- A map heatmap visual gradient is illustrative of sampled/interpolated forecast data, not a scientifically verified continuous radar field.
- Forecast data is not a real-time travel advisory and may miss road closures, surface condition, driver behavior, evolving events and model error; show restrained disclaimer.

## Boundary test matrix (minimum)

- Wind `24.999, 25, 34.999, 35, 44.999, 45, 54.999, 55` mph.
- Rain `0.0999, 0.10, 0.2499, 0.25, 0.4999, 0.50, 1.00, 1.0001` in/hr.
- Snow `0.4999, 0.50, 0.9999, 1.0, 1.9999, 2.0, 3.0, 3.0001` in/hr.
- Loads `30000, 30000.01, 40000, 40000.01` lb at 35, 44.999, 45, 54.999 and 55 mph.
- Missing/negative/NaN/infinite values, mismatched arrays, weather outside horizon, both endpoints, route shorter than spacing, partial last segment.
- Route ties, no-travel shortest route, all routes blocked, all routes unknown, uneven segment lengths and stability under 10/25/50 display selection.
