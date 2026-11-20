# 20 — README, GitHub and Loom delivery checklist

## GitHub repository

The final implemented repository should include actual frontend/backend source, dependency lockfiles, `.env.example`, Docker setup if chosen, migration files, tests, CI, architecture diagrams, design spec, provider attribution, license notes and a README with reproducible commands. Verify secret scan before pushing.

## README required sections

- Overview and screenshot of **actual** running UI.
- How assessment features map to code.
- Provider selection and why, weather units/risk policy, forecast/unknown limitations.
- Prerequisites, API key environment names (not values), local setup/start, test commands and live deployment URL.
- System architecture with Mermaid diagram and backend data flow.
- Known limitations: missing routes, incomplete weather, interpolation, truck vehicle parameter assumptions, public API quotas/licensing.
- Evidence from real test runs: commands and results.

## Loom script (5–10 minutes)

1. ~1 minute: product goal, tech stack and one-screen premium visual direction.
2. ~2 minutes: enter origin/destination, departure, weight; show 3 routes when genuinely returned (or explain fewer).
3. ~2 minutes: inspect weather checkpoint ETA, risk segments, load overrides and recommendation explanation.
4. ~1 minute: 0–48h corridor forecast slider, map smoothness and mobile layout.
5. ~1–2 minutes: architecture/services, test results and graceful unknown/No Travel states.
6. ~1 minute: deployment/setup, tradeoffs, limitations and future improvements.

Replace approximate timings as needed to stay within actual 5–10 min. Only show real app behavior, not a mock presentation claimed as a production system.

## Final release report template

```text
Commit/repository URL: [verified]
Hosted frontend URL: [verified]
API health URL: [verified]
Video URL: [verified]
Backend tests: [command + observed result]
Frontend tests: [command + observed result]
E2E run: [command + observed result]
Security/quality checks: [observed result]
Provider accounts/license: [mode, no secrets]
Known limitations/blockers: [explicit]
```
