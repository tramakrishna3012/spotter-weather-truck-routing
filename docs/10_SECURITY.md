# 10 — Security and privacy specification

## Threat model (MVP and scalable deployment)

Assets: provider keys, trip origins/destinations, load and departure time, internal queue jobs, user session, caching, deployment credentials. Threats: credential leak, cost exhaustion/quotas, arbitrary SSRF through tile/provider URLs, path/ID enumeration, cross-session plan read, unbounded provider fanout, malformed large GeoJSON, XSS through provider labels, SQLi/unsafe queries, stale/unverified forecast represented as safe, and sensitive coordinate logging.

## Mandatory baseline

- Store server-side provider tokens in env/secrets manager; never embed HERE or private weather API key in JS. Public tile tokens are only used if provider allows browser exposure, restricted by domain as applicable.
- HTTPS/TLS end-to-end, strict allowed hosts/CORS for real frontend origin, secure cookies if cookies used, CSRF protection for state-changing session endpoints, HSTS on production domain.
- DRF serializer/schema validation for all fields: numeric finiteness/ranges, coordinate bounds, location string length, allowed checkpoint spacing values, positive load, valid datetime/time zone, route length and provider response shape.
- Reject client-provided target URLs. All outbound HTTP destinations must be configured host allowlists; connect/read timeouts and maximum response bytes; disallow redirects to arbitrary hosts.
- Async workers use minimum IAM permissions and a separate worker credential where possible. Database credentials should not have superuser privileges.
- Prevent unauthenticated location/result access by scoped opaque authorization or signed session; check ownership on every plan, result and forecast endpoint, with nonenumerable IDs.
- Rate-limit and quota plan requests, geocoding, polling, tile-related proxy paths and weather fanout. Use per-IP and per-user/scope controls with burst and sustained thresholds; adapt to budgets.
- Escape/sanitize provider place labels and route description in React; avoid `dangerouslySetInnerHTML` for external text.
- Disable verbose debug, stack traces, admin pages and overly permissive CORS in production. Maintain dependency scanning and pins.
- Log request IDs, status and durations; scrub API tokens, exact coordinates, personal info and raw provider payloads by default.

## Authorization model choices

- The assessment doesn't require sign-in. Use ephemeral guest plans with an opaque bearer-like plan access token bound to an HTTP-only SameSite cookie or securely generated guest session; never treat plan ID as universal authorization.
- If multi-user accounts are later required, introduce org/tenant ownership and migrate access controls deliberately. Don't bolt on partial authentication and claim enterprise multi-tenancy.

## Safety-related security

Risk integrity is a security objective: reject invalid/negative weather data, missing hours, incoherent units and unknown policy versions. Ensure frontends cannot override `eligible`, `recommendation_status` or severity via client-submitted data. Record normalized source, issued time, policy version and data-coverage reason codes.

## Operational controls

CI: secret scanning, backend+frontend lint/typecheck/tests, dependency audit, SAST where available. Production: secrets rotation plan, least-privilege deployment, encrypted backups, defined data retention, audit of external provider terms, request throttling and incident rollback runbook.

## Verification

Test access to another session's plan, malformed GeoJSON/big payloads, unexpected provider redirects, repeated replay submissions, rate limits, old forecast misuse, impossible load input, invalid datetime and all error responses without leaking traces.
