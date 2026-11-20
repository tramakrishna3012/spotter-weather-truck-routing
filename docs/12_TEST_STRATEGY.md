# 12 — Verification and testing strategy

## Test pyramid

### Pure domain unit tests (first, highest priority)

- All wind/rain/snow threshold boundary values plus strict load rules (`>`, not `>=`).
- Worst-condition precedence; unknown/NaN/negative/time mismatch handling.
- Route sampling at 0, multiple checkpoints and final endpoint; routes shorter than spacing; distance-weighted aggregation equals route distance within numeric tolerance.
- ETA from provider timing vs documented fallback; correct UTC conversion with offsets/DST; forecast horizon/out-of-range.
- Recommendation order as lexicographic tuple; ties deterministic, blocked/unknown routes never recommended; 10/25/50 display spacing does not alter ranking.

### Provider adapter/contract tests

- HERE `transportMode=truck`, `alternatives=2`, proper vehicle options; 0/1/2/3 routes and duplicates; truck restriction warnings.
- Weather batched forecast with exact unit conversions and hourly indexing; missing variables, inconsistent lengths, timezone labels, 429, 5xx, timeout, malformed JSON.
- Geocoding ambiguity and geocoder rate limit. Map style/attribution permitted by provider license.
- Use deterministic captured fixtures with provenance, redacted keys. Never rely on live weather for stable unit tests.

### API integration tests

- Plan POST validation, idempotency; status progression; complete/blocked/partial results; cache TTL; cross-session access denial; cancellation (if supported); no leaked tracebacks.
- Race condition: double request with same key; worker retry during completion; stale result overwrites blocked.
- OpenAPI contract snapshots / generated TypeScript type check.

### Frontend interaction tests

- Autocomplete keyboard and screen reader semantics; clear and submit; departure timezone; weight validation.
- Selected route matches backend recommendation initially, then manual route changes are not mistaken for new backend recommendations.
- Fewer route card count exact; blocked/unknown/partial states clear; no stale 'safe' or recommendation badges.
- Checkpoint popover, map layer visibility, risk legend, forecast slider timestamp, mobile bottom sheet, reduced motion, focus restoration.

### E2E and visual testing

- Successful trip with three valid routes, valid two-route trip, all No Travel, partial weather, no route, provider unavailable.
- Desktop/tablet/mobile screenshots and manual review against `04_DESIGN.md`; check practical typography, low clutter, no fake metrics.
- Performance tracing for slider scrubbing and route selection; memory leaks and listener cleanup.
- Automated axe checks where available, manual keyboard navigation and contrast review.

### Security/load

- Cross-owner access, replay, auth/guest token scope, CORS/CSRF, redaction, secret scanning, malformed large inputs, repeated user flood and quota backpressure.
- Load tests on **stub provider** by default; opt in to live-provider load only with quota/budget approval.

## Quality gate commands (adapt to actual generated project scripts)

```text
frontend: install locked deps -> lint -> typecheck -> unit tests -> build -> Playwright E2E
backend: install locked deps -> lint/format -> typecheck if configured -> pytest -> migrations check -> app health
infrastructure: docker compose config -> service health -> smoke tests
```

No test pass should be claimed before execution. Store commands, logs/summary, failures and environment info in `docs/20_DEMO_AND_HANDOFF.md` after implementation.
