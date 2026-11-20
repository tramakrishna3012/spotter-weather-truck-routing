# 18 — Observability, reliability and user-load handling

## What to measure

| Signal | Useful dimensions | Action |
|---|---|---|
| `plans_started_total`, `plans_completed_total` | status, data mode, source | detect failures and false success |
| Plan latency p50/p95/p99 | total, routing, forecast, classification | identify bottleneck |
| Provider request latency / response codes | provider, endpoint, retry count | timeout, quota and backoff tuning |
| Queue depth / oldest waiting job | job type | scale workers with quota bound |
| Cache hit and stale counts | provider and data class | freshness and spend |
| Unknown/no-travel coverage | route count, policy version | distinguish safety uncertainty vs provider error |
| Frontend interaction latency/FPS | device class, route count, slider | map smoothness regressions |
| API request rate and throttles | scoped identity/IP aggregate | stop cost abuse |
| DB read query count and memory | endpoint | catch N+1 and leaks |

## Correlation and privacy

Generate opaque request IDs that propagate API -> worker -> provider adapter logs. Avoid logging raw origin/destination, full coordinates, precise plan geometry, actual HTTP credentials or entire weather payloads in production. Aggregate metrics and enforce bounded metric label cardinality; don't label metrics by trip IDs. Scrub exception messages before sending to analytics.

## Alert candidates

- Sustained large increase in provider 429/5xx or timeout rates.
- Job queue delay high compared to acceptable plan wait; provider cap saturation.
- Significant unexplained rise in `unknown` forecast coverage.
- Frontend crash or API readiness failure.
- New risk policy version emits divergent route ranks on regression fixture corpus.

## Monitoring integration choice

Use built-in Django structured logging and Prometheus-compatible metrics where available. Add OpenTelemetry traces/Sentry only when there's a concrete hosting fit; monitor real cost and PII retention. Dashboard URLs and credentials must not be hardcoded.

## Multi-user capacity test

Model the whole chain (request rate -> provider quotas -> jobs/checkpoints -> weather batching). Start with stubbed integrations and configurable concurrent plan workers. Prove isolation, bounded fanout, retry safety, no lost jobs and graceful backpressure. Do not claim support for a specific concurrent-user count without a repeatable measured test.
