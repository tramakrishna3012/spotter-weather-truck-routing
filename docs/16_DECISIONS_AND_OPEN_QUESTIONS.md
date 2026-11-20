# 16 — Architecture decision record and open questions

**Decision log rule:** Distinguish original assignment facts from proposed conventions. For a consequential change, write `ADR-###`, context, considered options, chosen option, consequences, owner/date, validation status. Do not silently rewrite established architecture.

| ID | Proposed decision | Status / follow-up |
|---|---|---|
| ADR-001 | React + TypeScript + Django/DRF modular monolith | Proposed; aligns with PDF React+Django |
| ADR-002 | HERE truck route alternatives | Proposed; verify account/quota and vehicle inputs |
| ADR-003 | Open-Meteo hourly forecast | Proposed; verify business license for commercial use |
| ADR-004 | MapLibre GL JS plus separately licensed basemap | Proposed; verify style/tile terms |
| ADR-005 | Scoring at conservative <=10mi internal resolution | Proposed; benchmark provider cost and hazard detection |
| ADR-006 | Display spacing 10/25/50mi separate from scoring | Proposed; unit-test invariance |
| ADR-007 | Exact overlapping threshold boundaries: half-open; strict > endpoints for No Travel | Proposed; test and document as PDF interpretation |
| ADR-008 | Worst adjacent hourly weather bin used for safety classification | Proposed conservative policy; document accuracy tradeoff |
| ADR-009 | Exclude unknown weather and No Travel routes from recommendation | Proposed fail-closed safety behavior |
| ADR-010 | Request primary + 2 alternatives; render actual result count | Proposed; consistent with HERE `alternatives` |
| ADR-011 | Guest access with scoped opaque session token | Proposed; no login needed for assessment |
| ADR-012 | Async job queue optional until measured | Proposed; maintain contracts for later scaling |
| ADR-013 | Stale weather invalidates safety recommendation | Proposed; define valid freshness per provider/model |
| ADR-014 | Time slider's reference instant is explicit and stable | Open choice: departure instant vs forecast snapshot |

## Open questions needing practical checks (not blockers to architecture docs)

1. Are the users always in a geography where HERE truck routing/coverage is adequate?
2. Is an account with paid/commercial weather use necessary now, or is it a noncommercial interview demonstration?
3. What licensed basemap provider/style/token is acceptable and compatible with selected routing data terms?
4. Are truck dimensions/gross weight available? The assessment only specifies payload weight for weather risk; don't invent dimensions.
5. How far into the future may departure be scheduled, and how should out-of-forecast-horizon trips be handled?
6. What exact model/time slice semantics will the 0–48h slider represent?
7. For a deployed public demo, how much anonymous usage and provider billing budget is available?
8. What local/hosting runtime versions exist in the repository?
9. Is storing results across sessions required? If not, use short-lived guest results.

## Review criteria for changes

Prefer reversible, measurable changes. Any architectural alteration must state its effect on risk correctness, user experience, provider costs, security, existing integrations and tests. The source assessment takes precedence over optional enterprise embellishments.
