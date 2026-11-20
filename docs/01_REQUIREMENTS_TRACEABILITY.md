# 01 — Requirements traceability

**Source of requirements:** `reference/fs-assessment-spotter.pdf`, pages 1–2. This file separates original requirements from our proposed engineering responses.

| ID | Assessment requirement | Expected implementation | Proof |
|---|---|---|---|
| R01 | Origin and destination | Geocoded origin/destination picker with coordinates | Form validation + E2E |
| R02 | Departure date/time | Timezone-aware input, send ISO 8601 offset or UTC | DST/offset tests |
| R03 | Load weight | Pounds and positive numeric validation | Boundary + invalid tests |
| R04 | Three routing options | Request 2 alternatives beyond optimal; accept fewer genuine results | Provider contract + dedup tests |
| R05 | Weather every 10/25/50 miles | User-selectable display checkpoints, including endpoints | Distance sampling tests |
| R06 | Forecast at estimated checkpoint arrival | ETA adjusted weather lookup, forecast horizon checking | Time alignment tests |
| R07 | Risk and load rules | Versioned backend policy, worst applicable risk per checkpoint | Exhaustive boundary tests |
| R08 | Prefer safer route with travel time tie-break | Severe miles, High miles, average score, then duration | Ranking tests |
| R09 | Map route options, checkpoints, severity, ETAs, summaries | MapLibre layers, list alternatives, selected state | UI/E2E + visual review |
| R10 | 0–48h corridor weather heatmap slider | Time slices along corridor, honest coverage and source timestamps | Slider E2E + map perf tests |
| R11 | GitHub repository | Reproducible source with README and no credentials | Repo inspection |
| R12 | Hosted application | Testable frontend/API links, environment health | Smoke test deployed URL |
| R13 | 5–10 minute Loom | Recorded walkthrough of real result and limitations | Video URL, manual review |
| R14 | UI/map/heatmap smoothness (40%) | Managed map layers, good interaction latency | Chrome profiles + device tests |
| R15 | Correctness of routes/weather/risk/recommendation (40%) | Robust domain services and error states | Test suite + fixture traces |
| R16 | Code quality (15%) | Typed DTOs, cohesive modules, linters, CI | Review + CI |
| R17 | Documentation and walkthrough (5%) | README, design decisions and video | Handoff verification |

## Supplied assessment policy (do not change)

Wind severity: Low <25 mph; Moderate 25–34; High 35–44; Severe 45–54; No Travel >=55. Rain: Low <0.10 in/hr; Moderate 0.10–0.25; High 0.25–0.50; Severe 0.50–1.00; No Travel >1.00. Snow: Low <0.5 in/hr; Moderate 0.5–1.0; High 1.0–2.0; Severe 2.0–3.0; No Travel >3.0. Additional wind overrides: >=55 mph No Travel regardless of load; 45–54 mph and load >30,000 lb No Travel; 35–44 mph and load >40,000 lb Severe.

Ranking order from source: (1) fewest Severe miles; (2) fewest High miles; (3) lowest average risk; (4) shortest travel time.

## Explicit engineering clarifications (not stated in source)

- Treat covered No Travel as disqualifying, not as a low numerical score.
- Treat insufficient required weather as unknown and ineligible for safety recommendation.
- Distinguish displayed checkpoints and internal conservative sampling so UI choice doesn't change safety rankings.
- Return fewer route choices honestly if the routing provider cannot supply three distinct truck routes.
- Resolve overlapping threshold endpoints consistently, verify and document with tests.
- Add transparent weather forecast uncertainty and attribution; it is not a guarantee of travel safety.

These clarifications are design proposals, not direct quotations from the PDF.
