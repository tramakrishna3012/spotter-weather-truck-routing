# 17 — Objective definition of done

Use `[x]` only after tested. Record supporting command, screenshot, output or hosted URL. This handoff ships with **all tasks unchecked** because implementation has not been performed.

## P0 — Correctness and functionality

- [ ] Origin and destination geocode correctly; ambiguous matches are resolved by user.
- [ ] Departure timezone/UTC conversion and load input validation work.
- [ ] HERE or approved truck router is called in truck mode for up to 3 genuine routes.
- [ ] Honest 0/1/2/3 result support; alternatives never fabricated.
- [ ] Display checkpoints work at 10, 25 and 50 miles and include route endpoints.
- [ ] Internal sampling and route score do not weaken with coarser display density.
- [ ] Forecast is queried at each checkpoint's estimated arrival time.
- [ ] Wind/rain/snow conversion uses provider-declared units and correct time alignment.
- [ ] Weather + payload risk policy passes every threshold boundary case.
- [ ] Severe/High/unknown/No Travel miles are length-weighted and sum correctly.
- [ ] No Travel/unknown route cannot be recommended as lower-risk eligible.
- [ ] Ordering is Severe miles > High miles > average risk > travel time with deterministic ties.
- [ ] All candidate routes and segmented hazards draw correctly on map.
- [ ] ETA and forecast source/valid-at times are distinguishable.
- [ ] 0–48h slider updates corridor forecast visualizations and respects gaps.

## P0 — Premium UI

- [ ] Original Spotter visual identity is respected; no Apple or Google asset copying.
- [ ] One clean map-first desktop layout; not a card-stuffed admin dashboard.
- [ ] Mobile touch-first sheet/map usable at 320–390px widths.
- [ ] Meaningful motion only, reduced-motion fallback and stable focus.
- [ ] Keyboard operable planner, selectors, cards, slider and alternatives to map-only information.
- [ ] Explicit idle/loading/partial/blocked/error/fewer-routes states.
- [ ] No fake live weather/route values or guarantee-safe copy.

## P1 — Engineering and delivery

- [ ] Tests for boundary, route sampling, ETA, unknown, tie-break and cross-user isolation pass.
- [ ] API contract and frontend TS types agree; lint/typecheck/build pass.
- [ ] Retry, timeout, bounded concurrency, caching and quota handling verified.
- [ ] Secrets uncommitted; production mode has restricted hosts/CORS and no fixtures.
- [ ] Performance profiled for route switches and heatmap slider; no map object leak.
- [ ] Source repo on GitHub with README and setup instructions.
- [ ] Hosted live frontend and API smoke tested; plan completion proven with providers.
- [ ] 5–10 minute Loom walkthrough created from actual app.
- [ ] Remaining limitations, provider costs and license choices disclosed.

## Evidence template

| Check | Evidence (command/URL/test ID) | Verified date | Status |
|---|---|---|---|
| Risk threshold tests | — | — | Not run |
| Frontend build | — | — | Not run |
| End-to-end route and weather | — | — | Not run |
| Live deployment | — | — | Not deployed |
| Mobile and reduced motion | — | — | Not reviewed |
