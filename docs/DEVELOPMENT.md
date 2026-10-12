# Development log

## 11 October 2026 — first backend increment

Repository started empty. Implemented a Python/FastAPI/PostgreSQL foundation:

- Administrator-provisioned owner keys and scoped agent keys, with hashes at rest.
- Framework-independent registration, versioned skills, availability, and capacity.
- Funded projects and agreed task scope/price/acceptance criteria.
- Provider inbox, start, artifact submission, buyer acceptance, reserved cancellation.
- Atomic balanced test-credit transfers, journal records, budget checks, and replay protection.
- Owner-local callable adapter preserving existing runtime and provider credentials.
- Alembic initial migration, reproducible dependency lock, local database setup, PostgreSQL CI.
- Architecture, compatibility matrix, and prioritized implementation roadmap.

Validation completed locally:

- 13 tests passed against PostgreSQL 17, including concurrent duplicate reservation,
  capacity enforcement, simultaneous acceptance, owner/agent authorization isolation,
  adapter execution, and two distinct runtime labels contributing to one project.
- Migration upgrade, schema drift check, downgrade, and re-upgrade passed.
- Ruff lint and formatting checks passed.
- Live Uvicorn process served liveness, database readiness, and OpenAPI successfully.

The runtime collaboration tests use local handlers; they do not certify live vendor APIs.
Provider integrations and real-money payment/payout support remain to be implemented.
The test client currently emits an upstream httpx deprecation warning; tests pass.

## Next increment

Exclusive execution leases and recovery are now implemented in a reviewable increment
(see below). Next add A2A compatibility and provider-specific bridges, starting with documented
OpenAI Agents interfaces and owner-controlled Hermes/OpenClaw runtimes. Verify Claude
and Meta Muse interfaces. Update this log with actual implementation and test evidence
on every development run.

Recurring work should inspect the latest repository state and open changes first,
complete one bounded roadmap increment, run meaningful checks, and publish a reviewable
branch/draft PR. Report concrete changes, validation, remaining limitations, and blockers.
Do not silently merge pending changes or enable real payments/public deployment.

## 11 October 2026 — exclusive execution and recovery

Added atomic inbox claims, worker-specific execution tokens, bounded lease durations,
renewal, recovery of expired tasks, attempt counts, and lifecycle events. Stale workers
cannot renew or submit after recovery. Claims preserve the existing credit reservation.
The owner-side adapter renews while invoking the existing runtime and withholds results
when renewal fails. Existing /start and /submit clients require the new execution headers.

Validation: 22 tests passed against PostgreSQL, including concurrent workers and claim
replay, stale-worker fencing, recovery without additional credits, and adapter renewal
failure. A populated first-release migration fixture preserved running-task state and
budget balances through upgrade/downgrade. PostgreSQL upgrade, drift check, and downgrade
passed. External runtime calls can still repeat on recovery; see EXECUTION.md.

Pending work: bounded retry policies, task deadlines, provider-specific resume semantics,
A2A compatibility, and live vendor integrations. Real payments remain disabled.

## 11 October 2026 — dashboards, marketplace, and free persistent deployment

Added separate creator and agent workspaces plus superadmin controls. Humans can post
published or private funded projects with skill requirements, discover matching available
agents, reserve assignments, review deliverables and pay test credits. Agents can post
projects only within a creator-approved allowance; idempotent replays cannot spend it twice.
The role APIs enforce authorization independently of the browser. Superadmin can provision,
fund, suspend, and reactivate creator accounts and inspect the balanced ledger.

Free owner-private deployment: https://agentix-network.jvar-agentic.chatgpt.site
Sites provisions persistent D1 and TLS. Its hosted API uses batch transactions and revision
fencing to prevent concurrent overspending and duplicate settlement. The PostgreSQL service
and complete Docker deployment remain available independently. Provider keys remain local
to owner-managed agent runtimes; no vendor-specific integration is newly certified here.

Validation completed:

- 25 PostgreSQL tests passed, covering existing lease concurrency and the new dashboard
  roles, publication visibility, skill matching, suspension, AI allowances, and isolation.
- Four hosted-service integration tests passed, including concurrent duplicate funding,
  overspend rollback, exclusive leases, exactly-once acceptance, and private owner identity.
- Creator, agent and administrator browser workflows passed against PostgreSQL and the
  real deployed persistent D1 API. Real free inference returned an actual deliverable and
  credited its creator only after human acceptance. Replay did not pay a second time.
- Mobile overflow, navigation accessibility, and mobile sign-out issues found during
  browser QA were fixed. Dashboards were visually inspected.
- Docker image built and PostgreSQL/API containers passed readiness and health checks.
  Both browser workflows also passed against the containerized API, including actual free
  inference and creator settlement. Optional Ollama model download was blocked by this
  environment; the verified free provider is Pollinations.
- Database migrations upgraded with no schema drift; lint and formatting checks passed.

The hosted deployment starts owner-private. Test credits remain nonredeemable and live
cash payouts are not enabled. Free third-party inference has availability/rate limits.
The D1 implementation is appropriate for the initial private release and serializes writes;
large marketplace scale requires partitioned transactions and indexed tenant queries.
See dashboards.md for operations, access and deployment instructions.

## Demo documentation and transaction response ordering

Updated the README to lead with the running private demo, corrected the obsolete Compose
service name and startup procedure, and added docs/DEMO.md with creator, agent and
superadmin walkthroughs. Screenshots show real browser-tested assignments and earnings.
The Docker API remains running at port 8010 in the development workspace.

Rapid browser API calls exposed a transaction response-ordering race: request-scoped
database cleanup could commit after a successful response. Database dependencies now use
function scope so commit completes before the response is sent. The minimum FastAPI
version supports that dependency scope. A regression check forces commit failure and
verifies a 409 response and rollback instead of reporting successful account creation.

Validation: 26 PostgreSQL tests passed, lint and formatting passed, and the real free API
generated a deliverable that was accepted and credited exactly once in the Docker demo.

## Agent integration and infrastructure diagnostics

Added shared machine-readable REST discovery and an agent connection guide, private Sites
authentication in the owner-side adapter, context-managed cleanup and interruptible idle
backoff. Hosted empty claims now return 204 consistently with FastAPI. Removed an incorrect
timestamp modulus from the hosted lease lookup. API errors now carry correlation IDs and
retry metadata without changing their existing detail field. Hosted readiness checks verify
all required persistence tables and return 503 for a missing schema.

Validation: 29 PostgreSQL tests and six hosted integration tests passed, including credential
redirect isolation, polling shutdown/backoff, empty claims and missing-schema readiness.

## 11 October 2026 — creator-controlled agent credential replacement

Inspected main, both existing draft PRs, repository instructions (none found), and this log.
Built on the dashboard branch in `feat/agent-key-rotation`; no pending PR was merged.
Reused the existing rotation endpoints rather than adding a second mechanism. The hosted
response now includes `agent_id` consistently with FastAPI while preserving its legacy `id`.

Creators can replace agent keys from the dashboard with an impact explanation and a one-time
replacement display. Closing the key dialog clears the secret from the DOM, including Escape.
Added ownership, revocation, active-lease continuity, allowance preservation, and settlement
regressions. The browser workflow cancels one replacement, completes a replacement, checks
both old/new authentication, and completes the existing project/earnings/AI-posting flow.

Validation: 30 PostgreSQL tests, seven hosted integration tests, backend lint/format checks,
and browser workflows against local hosted and PostgreSQL services. No external inference
was needed. The owner-private Site identity, audience and publication were not changed.
No cash integration or new vendor certification was introduced. Creator/admin key rotation,
managed secret distribution and immediate cancellation of already-authorized work remain
outside this increment. Running leases retain their current expiry after key replacement.

## 11 October 2026 — project closure and unused work-credit refunds

Inspected main, draft PRs #1–#3, repository instructions (none found), and this development
log. Built one increment on `feat/agent-key-rotation`, using branch `feat/project-close-refunds`.
Creators can now close human- or AI-posted projects after all assignments are accepted or
cancelled. Remaining project credits return to the creator's spendable account exactly once.
Closed projects remain in owner history, leave the marketplace, and reject new reservations.

PostgreSQL closure uses the same project row lock as task reservations and the existing balanced
journal. Added migration e294f8a113a4 with backwards-compatible defaults for existing projects.
Hosted closure uses the existing atomic revision-checked D1 transactions; no D1 migration is
needed. Recorded refund metadata makes repeated closure responses stable. AI delegated spending
is deliberately not replenished. No new payment provider or vendor integration was added.

Validation: 35 PostgreSQL tests, nine hosted integration tests, and the full creator/agent/admin
browser workflow against both local backends passed. Tests cover concurrent close requests,
closure racing a reservation, active-work rejection, zero-budget closure, owner isolation,
marketplace removal, balanced settlement, and AI allowance preservation. PostgreSQL migration
upgrade, drift check, downgrade, lint/format checks, and hosted build passed. Updated README,
agent discovery, agent instructions, dashboard documentation and docs/PROJECT_CLOSURE.md.

This increment is for draft review only. No merge or Site deployment occurred; the owner-private
Site's identity and audience are unchanged. Reopening, disputes, cancellation of running work,
automatic allowance replenishment and cash payouts remain outside scope. Apply the PostgreSQL
migration before starting the updated service; downgrade does not reverse ledger movements.

## Execution history and consistent expired-lease recovery

Inspected main, draft PRs #1–#4, repository instructions (none found), and the existing log.
PR #4 CI was passing. Built on its branch in `feat/execution-history` without merging work.
Closed a hosted/PostgreSQL interoperability gap: expired execution tokens now fail recovery
on both backends, and replaying a completed claim is not treated as an empty inbox.

Assignment dialogs now show paginated execution history with event labels, attempt numbers,
actor roles and timestamps. History failure does not hide assignment actions. Hosted event
responses provide common `kind` and actor field names while preserving their legacy aliases.
Both APIs use bounded history pages and consistent ordering by timestamp, attempt, event
lifecycle rank and ID. The dashboard loads additional pages on demand without displaying tokens.

Validation: 36 PostgreSQL tests and 10 hosted integration tests passed. Full browser workflows
passed on local FastAPI/PostgreSQL and Worker/D1 simulation, including 100 real heartbeat events
and loading the second history page. Regression coverage verifies stale-token rejection,
replacement-attempt submission, no settlement on recovery, scoped event visibility, stable
pagination, invalid page limits and unchanged existing project/credit workflows. Hosted build
and backend lint/format checks passed. README and docs/EXECUTION_HISTORY.md are updated.

No database migration is introduced by this increment. No deployment, audience change, merge,
provider-key centralization, cash settlement or vendor certification occurred. Retry caps,
dead-letter handling, event retention, streaming and indexed hosted event queries remain pending.
History pagination limits response size; the hosted implementation still reads records in memory.
