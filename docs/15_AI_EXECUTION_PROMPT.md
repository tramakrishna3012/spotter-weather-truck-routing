# 15 — Paste this into your coding agent

> **Task:** You are the principal full-stack engineer and UI engineering lead for **Spotter — Weather-Aware Truck Routing**. Implement the full assessment in this repository from end to end using the provided handoff files. I want an **Apple-level restrained, thoughtfully motion-designed, premium enterprise UI** that still feels like a genuinely usable operational tool, not an AI-generated dashboard. Use React + TypeScript and Django/DRF. Follow the real assessment, prioritize weather/routing correctness, and do not build unnecessary products/features.
>
> **Required reading before code:** `AGENTS.md`, `reference/fs-assessment-spotter.pdf`, `docs/04_DESIGN.md`, `docs/06_RISK_AND_RECOMMENDATION.md`, `docs/02_ARCHITECTURE.md`, `docs/07_API_CONTRACT.md`, `docs/13_IMPLEMENTATION_ROADMAP.md`, `docs/17_ACCEPTANCE_CHECKLIST.md`. Then use the remaining docs for security, testing, performance and integrations.
>
> **Inspect existing repo first:** Identify which modules, constructors, hooks, routes, services, configs, tests and deployments already exist. Extend and reuse them rather than rewriting. Preserve connected features and avoid breaking unrelated flows. Do not hardcode providers, endpoints, timing, styling or runtime limits. Centralize given assessment risk rules in a versioned backend policy. Architecture can be adapted if existing code already implements an equivalent boundary.
>
> **Implement in order:** repository audit; unit-tested risk engine with correct units, strict boundaries, payload overrides and unknown handling; truck route adapter requesting up to 3 genuine route choices; checkpoint distance sampling and estimated-arrival weather; time-aware classification, safe eligibility and ranking; clean versioned API; map-first responsive UI; checkpoints, segmented risks, route cards; 0–48-hour forecast corridor heatmap with honest time semantics; subtle premium motion and reduced-motion accessibility; caching/jobs/concurrency as necessary; security/load and error handling; automated tests; hosting; README and 5–10 minute walkthrough plan.
>
> **No fabricated results:** never use demo routes/weather as live. If credentials are absent, use only explicitly labeled fixture mode and report credential blockers; keep coding and automated testing. Never create a fake third alternative, and never recommend a route with No Travel or unknown critical weather. If provider data is unavailable, show a real unavailable state. The frontend must not independently recalculate safety.
>
> **Expected behavior:** Do actual implementation work, not just another plan. Work incrementally and run relevant checks after each integration. Use available tools to edit, run and validate the project. If an account/key/action is needed, report the variable/account and why; do not request secret values pasted into chat. Maintain a short progress record with files changed, tests run/results, current blockers and the next step. Produce exact command logs and final acceptance matrix; do not claim passing checks or deployment without verifying.
>
> **End goal:** a complete assessment-ready Spotter web app with a senior-engineer quality UI, server-owned correct risk logic, sensible scalability, strong failure UX, automated test coverage, working deployment and clean documentation.

## Fast kickoff command (human)

Copy all files from this handoff ZIP to the root of the intended project, then send your coding agent: **“Read AGENTS.md and docs/15_AI_EXECUTION_PROMPT.md, audit the repository, and execute the assessment implementation end to end. Prioritize real working results and report tested evidence.”**

## Guard against common agent failure modes

- Agent writes a new README only: not complete.
- Agent adds screenshots but no provider/data integration: not complete.
- Agent runs fixture data and says live weather works: not complete.
- Agent implements threshold rules in React and Django separately: reject.
- Agent picks fastest route even if blocked: reject.
- Agent makes beautiful cards but map lags on slider: not complete.
- Agent introduces three mock alternatives because provider returned two: reject.
- Agent asserts E2E, accessibility, deployment or API quota passed without tests: reject.
