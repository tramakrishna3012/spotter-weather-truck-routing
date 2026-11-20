# 11 — Performance budgets and optimization guidelines

**Principle:** Smooth map and 0–48-hour heatmap are explicitly worth 40% of assessment score together with other UI quality. Avoid performance promises without measurements. Choose target thresholds, measure on agreed device/network, then revise through ADRs.

## Proposed budgets (targets, not measured results)

| Indicator | Initial engineering target | Notes |
|---|---|---|
| Planner interaction | Input response visually within ~100 ms | No network dependency for typing |
| Route selection | Highlight response within ~150 ms | Map object remains mounted |
| Slider scrub | Consistent ~30–60fps on development test device | Coalesce event frames; don't request on every pixel move |
| Route card rendering | No layout shifts after initial data | Skeleton dimensions match final cards |
| API uncached plan | Instrument end-to-end p50/p95 | Depends on external services; avoid unverified SLA |
| GET completed plan | Local/cache path budget set after measurement | Query count bounded |
| Heatmap | Precomputed 0–48h slices cached selectively | No repeated full geodata transfer per frame |

## Frontend tactics

- Code-split heavy MapLibre where helpful; prefetch based on task; avoid delaying actual map at result time.
- One persistent MapLibre instance; update GeoJSON source data instead of unmount/rebuild.
- Use native line/circle/heatmap layers, simplify data at low zoom, throttle slider, and preserve selected route visibility.
- Memoize geometry calculations keyed by route/result version, not by unrelated UI changes.
- Cancel stale fetches with `AbortController`, use TanStack Query dedupe and stale-time in accordance with forecast freshness.
- Never load 49 full separate huge GeoJSON blobs into initial JS state without size profiling. Batch/generate compact slices on demand, cache and prefetch adjacent offsets.
- Use CSS transforms/opacity for tasteful motion; respect reduced motion; avoid expensive blur/backdrop/filter across the map.
- Test map panel on integrated graphics / mobile, not just developer desktop. Profile memory after repeated plans to catch leaked map listeners.

## Backend tactics

- Keep provider requests batched, bounded and asynchronous within worker. Prevent a single trip from launching unlimited weather calls.
- Cache normalized hourly weather using coordinate/time/model keys and TTL bounded by forecast freshness; deduplicate concurrent identical work with short locks.
- Cap route count, route distance/geometry size, checkpoint count and forecast lookup count by validated configuration.
- Avoid N+1 DB read queries. Serialize only screen-required data; use compressed responses where appropriate.
- Use separate read API and heavy route-planning compute so one slow provider doesn't block all users.
- Scale worker concurrency based on provider quota (not just CPU); use backpressure `429/503` with retry hints when saturated.
- Track actual provider latency, cache hit ratio, queue wait, number of points per request, responses by error code and cost per plan.

## Test method

Gather baseline on repeatable route fixtures and chosen browser/device sizes, then profile 10/25/50 UI marker densities, 0–48h scrubbing, all three visible routes, frequent route changes, invalid locations, rate-limited provider and 100+ concurrent synthetic sessions if quota and environment allow. Use mocked provider load tests to avoid accidental charges and respect limits.
