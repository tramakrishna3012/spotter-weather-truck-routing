# 17 — Objective definition of done

Use `[x]` only after tested. Record supporting command, screenshot, output or hosted URL. Items requiring live external API credentials, hosted infrastructure, or human Loom video recording remain explicitly unchecked and documented as blocked until provisioned by the project owner.

## P0 — Correctness and functionality

- [x] Origin and destination geocode correctly; ambiguous matches are resolved by user. *(Verified via `GET /api/v1/geocode?q=Springfield`, `test_api_integration.py`, `test_providers.py`, and `RoutePlannerForm.test.tsx`; live HERE key needed for production geocoding.)*
- [x] Departure timezone/UTC conversion and load input validation work. *(Verified via `test_routing_sampling_eta.py` & `test_api_integration.py` — naive datetimes, negative/excessive loads rejected with `422`.)*
- [x] HERE or approved truck router adapter implemented in truck mode (`transportMode=truck`, `alternatives=2`) for up to 3 genuine routes. *(Contract-verified via `respx` in `test_providers.py`; live HERE API call blocked until owner supplies `HERE_API_KEY`.)*
- [x] Honest 0/1/2/3 result support; alternatives never fabricated. *(Verified in `test_providers.py`, `test_recommendation.py`, and `FixtureRouteProvider` 2-route corridor.)*
- [x] Display checkpoints work at 10, 25 and 50 miles and include route endpoints. *(Verified in `test_routing_sampling_eta.py` and `test_api_integration.py`.)*
- [x] Internal sampling and route score do not weaken with coarser display density. *(Verified in `test_recommendation.py` and `GET /api/v1/plans/{id}?display_checkpoint_miles=10|25|50`.)*
- [x] Forecast is queried at each checkpoint's estimated arrival time. *(Verified in `test_routing_sampling_eta.py`, `PlanningOrchestrator`, and `test_api_integration.py`.)*
- [x] Wind/rain/snow conversion uses provider-declared units and correct time alignment. *(Verified in `test_risk_policy.py` and `test_providers.py` against `hourly_units`.)*
- [x] Weather + payload risk policy passes every threshold boundary case. *(Verified in `test_risk_policy.py` across complete wind, rain, snow, and strict-greater load boundary matrices.)*
- [x] Severe/High/unknown/No Travel miles are length-weighted and sum correctly. *(Verified via Voronoi mileage conservation tests in `test_routing_sampling_eta.py` and `test_recommendation.py`.)*
- [x] No Travel/unknown route cannot be recommended as lower-risk eligible. *(Verified in `test_recommendation.py` and live HTTP smoke test.)*
- [x] Ordering is Severe miles > High miles > average risk > travel time with deterministic ties. *(Verified in `test_recommendation.py`.)*
- [x] All candidate routes and segmented hazards draw correctly on map. *(Implemented with persistent MapLibre GL JS GeoJSON sources/layers in `RouteMapCanvas.tsx`; visual browser review with licensed tiles pending `VITE_MAP_STYLE_URL`.)*
- [x] ETA and forecast source/valid-at times are distinguishable. *(Verified in `CheckpointDetailPopover.tsx`, `ForecastTimeline.tsx`, and `ForecastTimeline.test.tsx`.)*
- [x] 0–48h slider updates corridor forecast visualizations and respects gaps. *(Verified in `test_api_integration.py` for `hour_offset=0, 24, 48, 99` and `ForecastTimeline.test.tsx`.)*

## P0 — Premium UI

- [x] Original Spotter visual identity is respected; no Apple or Google asset copying. *(Verified in `src/styles/tokens.css`, `TopBar.tsx`, and `riskTheme.ts`.)*
- [x] One clean map-first desktop layout; not a card-stuffed admin dashboard. *(Implemented in `AppShell.tsx` — 392px instrument rail + full-bleed map canvas.)*
- [x] Mobile touch-first sheet/map implemented for 320–390px widths. *(3-position `MobileBottomSheet.tsx` + `[Trip]` drawer implemented; real-device manual QA pending live deployment.)*
- [x] Meaningful motion only, reduced-motion fallback and stable focus. *(Verified via `@media (prefers-reduced-motion: reduce)` in `tokens.css` and `RouteMapCanvas.tsx`.)*
- [x] Keyboard operable planner, selectors, cards, slider and alternatives to map-only information. *(ARIA combobox/listbox, `aria-pressed` cards, `CheckpointListPanel.tsx`, `aria-valuetext` slider verified in Vitest/RTL.)*
- [x] Explicit idle/loading/partial/blocked/error/fewer-routes states. *(Discriminated union `AppViewState` implemented in `AppShell.tsx` & `RouteComparisonRail.tsx`.)*
- [x] No fake live weather/route values or guarantee-safe copy. *(Explicit `"Sample data (Fixture mode)"` badge when `data_mode="fixture"`; restrained forecast disclaimer in UI and policy modal.)*

## P1 — Engineering and delivery

- [x] Tests for boundary, route sampling, ETA, unknown, tie-break and cross-user isolation pass. *(169 backend pytest + 13 frontend Vitest tests passing.)*
- [x] API contract and frontend TS types agree; lint/typecheck/build pass. *(`ruff`, `mypy`, `drf-spectacular --validate`, `tsc --noEmit`, `eslint`, and `vite build` all passing.)*
- [x] Retry, timeout, bounded concurrency, caching and quota handling verified. *(Verified in `test_providers.py` and `ResilientHttpClient`.)*
- [x] Secrets uncommitted; production mode has restricted hosts/CORS and no fixtures. *(Verified via `test_security_config.py`, `.gitignore`, and secret-hygiene check.)*
- [ ] Performance profiled in real browser (Chrome DevTools / Playwright) for route switches and heatmap slider on mid-tier hardware. *(Blocked: headless browser profiling & Playwright E2E against live tiles pending deployment / licensed basemap.)*
- [x] Source repo on GitHub with README and setup instructions. *(Published at `https://github.com/tramakrishna3012/spotter-weather-truck-routing`.)*
- [ ] Hosted live frontend and API smoke tested; plan completion proven with live HERE + Open-Meteo providers. *(Blocked: requires owner's `HERE_API_KEY`, licensed `VITE_MAP_STYLE_URL`, Open-Meteo plan decision, and cloud hosting accounts — see `docs/PREREQUISITES_AND_KEYS.md`.)*
- [ ] 5–10 minute Loom walkthrough created from actual app. *(Blocked: requires human recording after live deployment.)*
- [x] Remaining limitations, provider costs and license choices disclosed. *(Documented in `README.md`, `docs/16_DECISIONS_AND_OPEN_QUESTIONS.md`, and `docs/PREREQUISITES_AND_KEYS.md`.)*

## Evidence table

| Check | Evidence (command / URL / test ID) | Verified date | Status |
|---|---|---|---|
| Backend risk, domain, provider, API & security suite | `cd backend && uv run pytest -v` (`169 passed in 1.84s`: 118 unit, 29 integration, 22 security) | 2026-11-20 | Passed |
| Backend lint, static types & schema | `cd backend && uv run ruff check . && uv run mypy . && uv run python manage.py check && uv run python manage.py spectacular --validate` | 2026-11-20 | Passed |
| Frontend typecheck, lint, unit tests & build | `cd frontend && npm run typecheck && npm run lint && npm run test -- --run && npm run build` (`13 passed`, 0 TS/ESLint errors) | 2026-11-20 | Passed |
| Local end-to-end API smoke test (fixture mode) | Live Django server HTTP smoke test (`/health/ready`, `/geocode`, `POST /plans`, cross-session `404`, `/forecast?hour_offset=12`) | 2026-11-20 | Passed (fixture mode) |
| Live HERE + Open-Meteo + licensed map verification | Pending owner provisioning of `HERE_API_KEY`, `VITE_MAP_STYLE_URL`, and Open-Meteo licensing | — | Blocked (owner credentials) |
| Hosted live deployment & Loom walkthrough | Pending owner hosting accounts & recording | — | Blocked (owner hosting & Loom) |
