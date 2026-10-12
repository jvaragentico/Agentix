# Private response caching

Both backends return `Cache-Control: no-store` for `/v1/` API responses and `/health/`
checks, including successful reads, one-time credentials, empty claims, validation and
permission errors, and unavailable or unexpected-error responses. This prevents compliant
HTTP caches from retaining these responses. Health results must reflect current readiness.
The dashboard uses `fetch(..., {cache: "no-store"})` for API calls, bypassing browser HTTP
cache reads and writes as creators, agents and administrators switch workspaces.

FastAPI previously omitted this policy on successful private reads and credential creation;
the hosted API already protected its normal responses. The shared hosted boundary now also
protects health responses. Unexpected FastAPI exceptions return a generic `Internal error`
with request correlation, `retryable: false`, and `nosniff`, matching hosted behavior without
returning exception text. Server-side exception reporting remains the server's responsibility.

This is HTTP cache control, not encryption, credential revocation, an authorization boundary,
or a guarantee that a client cannot save a response. It does not purge historical proxy
caches, clear session storage, prevent screenshots, or control browser history snapshots.
Maintain scoped authentication, private Site access, TLS and trusted proxy configuration.
Do not override these headers with shared CDN caching rules for the private API. No new
proxy configuration or deployment was performed as part of this increment.

## Evidence and limits

Backend tests cover credential creation, wallets, task reads, empty claims, 401/403/404/422/413,
health success/failure and unexpected 500 errors. A forced FastAPI exception verifies that
private exception text is absent and its request ID matches the response header.

The creator/agent/admin browser workflow checks every observed API response for `no-store`
while exercising account switching, key replacement, project posting, execution, history,
acceptance, earnings, project refunds and delegated AI spending. It passes against local
FastAPI/PostgreSQL and hosted Worker/D1 simulation. These checks verify application and local
browser behavior; they do not certify the live hosting edge or production D1 behavior.

No schema, provider integration, credit semantics, Site identity or audience change is required.
