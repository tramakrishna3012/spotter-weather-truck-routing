# 03 — Senior frontend engineering specification

The visual north star is `04_DESIGN.md`. Engineering translates it into maintainable, accessible, data-true components. Do not replace domain logic with frontend calculations.

## Suggested component tree

```text
AppShell
 ├── TopBar (brand, units, minimal tools)
 ├── TripPlannerPanel
 │    ├── LocationField x2 (accessible provider autocomplete)
 │    ├── DepartureField (timezone explicit)
 │    ├── LoadWeightField (lbs and validation)
 │    ├── CheckpointSpacingControl (10/25/50 miles, display)
 │    └── PlanAction + form feedback
 ├── ResultsSidebar
 │    ├── RouteSummary and risk explanation
 │    ├── RouteComparisonCard x actual route count
 │    └── CheckpointDetailsPanel
 ├── RouteMapCanvas (single persistent MapLibre instance)
 │    ├── AlternativesLayer
 │    ├── SelectedRouteSegmentsLayer
 │    ├── CheckpointSourceLayer
 │    └── WeatherCorridorHeatmapLayer
 ├── ForecastTimeline (0–48 hours)
 └── GlobalStatusRegion (loading/error/coverage warnings)
```

## Frontend state boundaries

- **URL state:** optional shareable non-sensitive selected route/time; do not encode unprotected origins, precise locations or access tokens in URL.
- **Server state:** TanStack Query for plan submission/status/result, cancellation and freshness. Do not fetch per checkpoint from client.
- **UI state:** selected route, open detail, display checkpoint density, selected slider hour, visible layers, unit preferences.
- **Form state:** controlled or form-library values with schema validation; avoid mirrored duplicate stores.
- **Derivations:** view models transform unit labels, strings and presentational grouping, not risk thresholds.

## Performance-sensitive map rendering

Keep a single map object via `useRef` with deterministic lifecycle. Sources and layers are initialized once and updated with GeoJSON/vector data only when needed. Separate map imperative operations from React rerender paths. Move high-frequency slider state updates behind `requestAnimationFrame`/throttling and only change the relevant source. Keep label and route geometry payloads minimal. Avoid re-creating MapLibre instance on selection/time changes.

Use stable normalized result DTOs; memoize expensive geometry conversion rather than indiscriminately memoizing every component. For many checkpoints, cluster/aggregate visually at low zoom but preserve full data in the list or accessible detail view. Render text/list accessibility equivalents to map-only content.

## Thoughtful premium behavior

- Composed typography, deliberate whitespace, deep-teal accent tied to Spotter visual cue, readable risk colors.
- Three-layer spatial hierarchy (canvas, work panel, modal/popover) and subtle shadow; not literal 3D.
- Route selection transition 160–250 ms *when appropriate*; do not animate the hazard classification itself into a different category.
- Slider should feel responsive, but weather values may update only when the forecast slice is available; show an honest timestamp and loading state.
- `prefers-reduced-motion` disables non-essential transitions. Keep focus stable after async result updates.
- Avoid giant hero sections in the operational workspace; map and task are more important than decorative scenes.

## UI states that must be implemented

`idle`, `validating`, `geocoding`, `planning`, `partial_coverage`, `results_eligible`, `no_eligible_route`, `no_routes`, `provider_unavailable`, `forecast_out_of_range`, `stale`, `failed`, `canceled`. For each state: visible copy, screen-reader announcement strategy, CTA and safe map visibility. See `05_USER_FLOWS.md`.

## API typing and contract

Generate TS types from backend OpenAPI if possible, otherwise a manually reviewed canonical interface verified by contract tests. Keep `unknown` coverage distinct from zero risk; ISO UTC timestamps plus timezone label; route distance in meters internally; wind/rain/snow with explicit units on API boundary. Never silently coerce `null` to 0.

## Device review

Desktop 1440/1280/1024 widths; tablet 768; mobile 390/375/320. On mobile use a map with bottom sheet, not a scaled sidebar. Check orientation changes, virtual keyboard overlap, large font settings and safe-area insets. No horizontal scroll for primary flows. Build real `<button>`, `<form>`, `<label>` rather than clickable divs.

## Frontend folder proposal

```text
frontend/src/
  app/{router,providers}/
  features/trip-planner/{components,hooks,types}/
  features/route-results/{components,hooks,types}/
  features/weather-timeline/{components,hooks,types}/
  features/map/{components,layers,adapters}/
  shared/{api,components,config,styles,utils}/
```

Adapt to existing conventions if a project already exists; no forced migration.
