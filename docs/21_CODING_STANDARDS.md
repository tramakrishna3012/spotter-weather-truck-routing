# 21 — Enterprise coding and review standards

## Engineering rules

- Favor small cohesive functions, constructor-injected providers/services and explicit interfaces. Domain code should not import provider SDK or HTTP framework specifics.
- Reuse existing constructors, functions, components, utilities and routes. Check connected features before edits; preserve API compatibility or add migrations/tests.
- Never scatter hardcoded timeouts, locations, routes, tokens, UI spacing or eligibility rules. Use centralized versioned policy for original assessment thresholds; validated environment configuration for operational settings; shared design tokens for UI.
- Prefer readable deterministic algorithms over premature abstractions. Don't add a generalized plugin framework for two providers.
- Use typed responses/errors; use strict TS options and Python type annotations where it improves safety. Avoid `any` or unvalidated dynamic provider JSON across core domain boundaries.
- Validate at entry points and provider adapters, then use normalized invariants internally. Do not silently coerce missing weather to zero.
- Make requests idempotent, cancellation explicit and retries safe. No unbounded loops, workers or fanout.
- No production simulation switch that makes demo values appear live.
- Add a test for every fixed bug, especially around route ranking and presentation of unknown values.
- Keep JSX render functions compact, API hooks separate from components, and imperative map updates isolated. Use shared spacing/color typography tokens rather than one-off bespoke styling.
- Maintain security hygiene: no credentials in source, no broad CORS, no cross-user trip access, no externally controlled HTTP hosts.

## Definition of a good pull request

Explain problem, approach, compatibility impact, data and privacy changes, source of risk rules, changed files, tests run, screenshots for UI and deployment implications. No generic 'works fine' assertions.

## Review sequence

1. Read diff and trace complete UI -> API -> provider -> risk -> result path.
2. Check type and schema validation; no double implementation of risk in frontend.
3. Test all boundaries and unsafe/unknown cases.
4. Review provider expenses/license assumptions and rate limits.
5. Review map performance, responsive UI, keyboard and reduced motion.
6. Verify existing paths still work and dependency versions are supported.
7. Require concrete evidence before merge.
