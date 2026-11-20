# AGENTS.md — Authoritative Instructions for Spotter Coding Agents

## Mission
Implement the full weather-aware truck routing assessment in `reference/fs-assessment-spotter.pdf`, with the premium design direction in `docs/04_DESIGN.md`. Deliver a usable, deployable React + Django application, not a superficial demo or screenshots.

## Execution contract
1. **Inspect before modifying.** Read the repository tree, dependencies, routing, existing constructors, hooks, services, tests and environment. Reuse working code. Do not replace a functional flow to fit a preferred framework or library.
2. **Work end-to-end.** Make each vertical slice functional from UI to backend to provider adapter or clearly flagged fixture; add tests; confirm old flows still pass.
3. **No hardcoded operational values.** Endpoints, provider selection, TTLs, request limits, timeouts, sampling defaults, UI tokens and feature flags live in validated configuration. The explicitly required assessment threshold values live in a versioned policy object, not scattered literals.
4. **Never invent live results.** No mock routing/weather used as live data. Fixture mode is permitted for tests and local visual development but must be visibly labeled and cannot be enabled in production.
5. **Safety is backend-owned.** Frontend renders backend-derived risk, coverage, recommendation and reasons. It must not independently apply thresholds or claim an unverified route is safe.
6. **Do not forge three routes.** Request 1 primary + 2 alternatives; deduplicate realistic geometry; expose an honest fewer-routes state.
7. **Fail closed.** Unknown required weather, missing checkpoint ETA, provider mismatch, no-travel segment or expired forecast must prevent an unjustified 'recommended' label.
8. **Preserve local context.** Do not delete user data, rewrite Git history, publish secrets, commit `.env`, or make destructive infrastructure changes.
9. **Protect external integrations.** Timeouts, retries with jitter, bounded parallelism, provider quotas, caching, bulkheads, idempotency and failure-specific UI messages are required before production claims.
10. **Use pragmatic architecture.** Modular Django monolith + DRF, independently scalable workers if measured need. No unnecessary microservices, Kafka, Kubernetes or auth system for the MVP.
11. **Premium means restraint.** Follow `docs/04_DESIGN.md`: typographic precision, honest content, map-first layout, calm depth, purpose-driven motion; no visual gimmicks or brand imitation.
12. **Accessible by default.** Keyboard support, sufficient contrast, visible focus, alternatives to map-only meaning, reduced-motion support, labeled errors and real loading states.
13. **Test boundaries and integration.** Automated wind/rain/snow boundary tests, load rules, timezone conversions, route ordering, no-route, no-weather, network faults, responsive UI, E2E and regression.
14. **Report evidence.** At each milestone, state changed files, commands run, results, remaining blockers and next step. Never claim a pass you did not execute.
15. **Do not wait for unnecessary clarification.** Select conservative documented defaults for reversible choices and record them in `docs/16_DECISIONS_AND_OPEN_QUESTIONS.md`. Only require human action for real external accounts, credentials, licenses, domains or destructive operations.

## Document order and conflict resolution

1. Original assessment PDF controls required features and risk semantics.
2. `docs/06_RISK_AND_RECOMMENDATION.md` is the proposed executable resolution of boundary ambiguity and unknown conditions; write tests to it and flag any conflict with the PDF.
3. `docs/04_DESIGN.md` controls art direction and motion semantics.
4. Other handoff docs are implementation proposals and may be revised with an ADR after validating current code/provider capabilities.
5. Source code and test results are authoritative for **what actually works**, not for what the spec requires.

## Mandatory build sequence

Read `docs/00_START_HERE.md` -> inspect existing repo -> propose minimal changes -> validate key provider contract/units -> implement core risk unit tests -> request/normalize routes -> ETA/forecast -> aggregation/ranking -> API -> frontend planner/map -> corridor heatmap/slider -> UX states/accessibility -> security/performance -> E2E -> hosted deployment/demo.

## Completion gate

Do not say 'done' until items in `docs/17_ACCEPTANCE_CHECKLIST.md` have verified evidence or are explicitly marked blocked with a reason. Provide real hosted URL only if it exists. Never invent test output, provider data, or video link.
