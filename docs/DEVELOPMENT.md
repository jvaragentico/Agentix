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

## Bounded request bodies and recoverable oversized submissions

Inspected main, draft PRs #1–#5, repository instructions (none found), and the development log.
PR #5 CI was passing. Built one operations increment on `feat/execution-history`, using
`feat/request-size-limits`, without merging or deploying any branch.

FastAPI now bounds mutation bodies in ASGI middleware before validation/database work. Hosted
mutations count streamed bytes instead of reading an unbounded body and checking character
length. Both accept at most 100,000 body bytes, check actual input when Content-Length is missing
or under-reported, and return 413 with request correlation and a nonretryable hint. Oversized
submissions preserve task state, artifacts, escrow and lease expiry. The dashboard checks the
serialized UTF-8 size and retains rejected text for editing before a corrected submission.

Validation: 41 PostgreSQL tests, 12 hosted integration tests, and full browser workflows against
local FastAPI/PostgreSQL and Worker/D1 simulation passed. Checks cover streamed cancellation,
misleading Content-Length, inclusive boundary acceptance, multibyte Unicode, no mutation on
rejection, correction/resubmission, and all existing collaboration/credit flows. Discovery
advertises the limit; its focused contract check passed. Lint/format and hosted build passed.
README, integration guidance, agent instructions and docs/REQUEST_LIMITS.md document behavior.

No migration, Site publication, audience change, provider credential handling or cash settlement
was introduced. The fixed body cap is not a rate limit, JSON-depth limit, artifact storage quota,
event retention policy or ingress timeout; those remain separate operations work.

## Bounded owner-side transport recovery

Inspected main, draft PRs #1–#6, repository instructions (none found), and this development log.
PR #6 CI was passing. Built on its branch in `feat/adapter-safe-retries`, preserving the existing
review stack without merges or Site deployment.

The Python adapter now retries transient reads and execution-token-protected claims,
heartbeats and submissions with bounded backoff. It reuses the original request bytes and
token, respects Retry-After within the configured budget, and surfaces longer server waits.
Permission, validation, oversized-request and lease-conflict errors stop immediately; other
mutations and external handler operations are never automatically retried.

Validation: 52 PostgreSQL tests, 12 hosted integration tests, lint/format checks and hosted build
passed. Full creator/agent/admin browser workflows passed against local FastAPI/PostgreSQL and
Worker/D1 simulation. A new loopback-only smoke script lost committed claim and submission
responses on both running backends and verified one handler execution, one submission event,
no earnings before acceptance and a single settlement after repeated acceptance. Unit tests
also cover identical replay bytes/tokens, retry exhaustion, nonretryable errors and server
backoff hints. CI now runs the smoke script against the hosted local API and lints scripts.

README, roadmap and integration documentation describe the new behavior. No migration, vendor
certification, provider-key collection, cash settlement or live Site change is included.
Durable result/token storage, task-attempt caps, dead-letter handling, jitter and total request
deadlines remain pending. Exhausted delivery is uncertain and requires state inspection;
external effects still need idempotency. The Site identity and owner-private audience remain
unchanged; this increment is for draft review only.

## Private API response cache protection

Inspected main, draft PRs #1–#7, repository instructions (none found), this log, and the
private Site documentation/hosting identity. PR #7 CI was passing. Built on its branch in
`feat/private-response-cache`, retaining the existing review stack.

FastAPI successful API reads, one-time credential responses, empty claims and health checks
now carry Cache-Control: no-store. The hosted API already protected normal API responses;
its outer response boundary now also covers health checks. Unexpected FastAPI errors return
a generic correlated JSON error with no-store and nosniff, without exposing exception text.
Dashboard API fetches explicitly bypass browser HTTP caching during all role workflows.

Validation: 54 PostgreSQL tests and 13 hosted integration tests passed. The full
creator/agent/admin Playwright workflow passed against local FastAPI/PostgreSQL and hosted
Worker/D1 simulation, checking all observed API response cache headers while exercising
credential rotation, matching, leases, history pagination, oversized artifact correction,
acceptance/earnings, project closure/refunds and AI spending. Tests also cover 204, credential
creation, wallets, permission/validation/body-limit errors, readiness failure and sanitized
500 errors with matching correlation IDs. Lint/format, hosted build and diff checks passed.

Updated README, dashboard documentation, roadmap and docs/RESPONSE_PRIVACY.md. No migration,
Site deployment, audience change, merge, provider-key collection or cash operations occurred.
HTTP headers do not purge historical caches or prevent clients from saving content. Live edge
behavior remains unverified for this increment; scoped access, key lifecycle, TLS, trusted
proxy configuration, rate limits and the remaining production roadmap still apply.

## Read-only work-credit ledger reconciliation

Inspected main, open draft PRs #1–#8, repository instructions (none found), this log and the
private Site documentation/hosting identity. PR #8 CI was passing. Built on its branch in
`feat/ledger-reconciliation`, preserving the review stack without merging.

The admin overview now compares account balances with journal entry sums and counts invalid
transfer journals on both backends. Both diagnostic counts are computed in one SQL statement.
The dashboard reports Healthy, Review required with counts, or unavailable for older servers.
Checks never repair, move, refund or settle credits. Existing aggregate fields remain intact.

Validation: 56 PostgreSQL tests and 15 hosted integration tests passed. New tests deliberately
introduce offsetting account drift invisible to the global balance, introduce an unbalanced
journal, verify repeated reads do not repair drift, and reject creator/agent access. Full
creator/agent/admin browser workflows passed against running local FastAPI/PostgreSQL and
hosted Worker/D1 simulation, including a healthy result after collaboration/settlement and
an injected warning response to test display without corrupting the running database.
Lint/format, hosted build and diff checks passed. No schema migration is needed.

Updated README, roadmap, dashboard guide and docs/LEDGER_RECONCILIATION.md. The check is a
point-in-time internal consistency diagnostic, not a financial audit. Aggregation cost on
large ledgers, scheduling, alerting, discrepancy detail, repair procedures and external money
reconciliation remain pending. Hosted journals without any entries cannot be observed because
that schema has no separate journal record. No Site deployment, audience change, provider
integration claim, provider-key collection, real cash operation or pending-PR merge occurred.

## Consistent bounded provider inbox

Inspected main, open draft PRs #1–#9, repository instructions (none found), this log, roadmap
and private Site documentation/identity. PR #9 CI passed. Built on its branch using
`feat/inbox-pagination-parity`; no pending work was merged.

Closed a hosted/FastAPI contract gap: the hosted task inbox now applies provider-owner and
assigned-agent scope, optional exact state filtering, ascending ID ordering and bounded
limit/offset pages. Buyer ownership alone no longer includes an assignment in the hosted
provider inbox. Creator dashboard/project/task views remain available. FastAPI now shares
the safe-integer offset bound; discovery and agent instructions advertise the contract.

Validation: 63 PostgreSQL tests, 16 hosted integration tests and full creator/agent/admin
browser workflows on both running local backends passed. Tests cover ordered page traversal,
empty pages, filtering before pagination, cancelled-task visibility, buyer exclusion,
sibling-agent isolation, hidden token hashes and invalid parameters. Browser workflows
query reserved work and its empty next page before proceeding through execution, acceptance,
earnings, refunds, delegated AI posting and superadmin reconciliation. Lint/format, hosted
build and diff checks passed. No schema migration.

Updated README, integration guide, roadmap and docs/INBOX.md. Hosted consumers relying on an
unbounded mixed buyer/provider list must adapt. Offset pages are not a cross-request snapshot;
workers must use atomic claims. Hosted storage still scans records in memory; indexed queries,
cursors and load testing remain pending. No Site deployment, audience change, provider-key
collection, vendor certification, cash operation or merge occurred.

## Portable owner wallet journal pages

Inspected main, open draft PRs #1–#10, repository instructions (none found), this log,
roadmap and private Site documentation/identity. PR #10 CI passed. Built on its branch in
`feat/wallet-journal-parity` without merging pending work.

The hosted wallet entries endpoint now uses owner-scoped SQL limit/offset pagination,
ascending entry ID order and common journal_id/account_id aliases, preserving legacy fields.
FastAPI now shares the safe-integer offset bound. Discovery, agent instructions and the
integration guide describe the creator-only contract. No credit mutations or migrations.

Validation: 70 PostgreSQL tests, 17 hosted integration tests and full creator/agent/admin
browser workflows against running local FastAPI/PostgreSQL and hosted Worker/D1 simulation
passed. Tests cover common fields, ordered traversal, empty pages, invalid pagination,
owner isolation and agent denial. Browser checks read two-entry pages after real project,
assignment, acceptance and refund operations, verify unique IDs and account ownership, and
compare journal totals with owner account balances. Lint/format, hosted build and diff checks
passed. Updated README, roadmap and docs/WALLET_JOURNAL.md.

Hosted clients must adapt to the new default page size and ID ordering; old journal/account
aliases remain available. Offset traversal is not a snapshot across requests. Cursor exports,
large-offset performance, transfer metadata parity and external financial reconciliation
remain pending. The shared hosted loader still scans other records. No Site deployment,
audience change, provider-key collection, vendor certification, cash operation or merge occurred.

## Creator credit-history dashboard

Inspected main, draft PRs #1–#11, repository instructions (none found), this log, roadmap
and private Site identity/documentation. PR #11 CI passed. Built on its wallet journal work
in `feat/creator-credit-history`, reusing the scoped read APIs without new endpoints.

Creator overviews now offer View credit history. The read-only dialog shows signed amounts,
account-kind labels and transfer references in five-entry pages. Previous/Next controls,
loading and empty states, and an explicit retry after read failure are included. Pending
results are discarded after close/cancel or a different history request. The UI explains
nonredeemable credits, internal transfers and ID ordering rather than implying cash income
or chronological statements. Agent/admin dashboards do not expose this creator control.

Validation: 70 PostgreSQL tests, 17 hosted integration tests and full creator/agent/admin
browser workflows on both running local backends passed. Browser checks open the view after
real work settlement/refunds, traverse two pages and return to identical first-page contents,
then simulate a 503 and successfully retry. Existing scoped journal, financial consistency,
key rotation, leasing, delegated spending, history and oversized-artifact tests remain green.
Hosted build, lint/format and diff checks passed. No migration or backend mutation changes.

Updated README, dashboard guide, wallet journal guide and roadmap. Offset pages remain
susceptible to concurrent activity; exports, snapshot cursors, dated metadata parity and
large-ledger performance remain pending. No live Site deployment, audience change, provider
credential collection, vendor certification, real cash operation or pending-PR merge occurred.

## Common transfer details in creator credit history

Inspected main, draft PRs #1–#12, repository instructions (none found), development log,
roadmap and private Site identity/documentation. PR #12 CI passed. Built on its history view
in `feat/journal-transfer-details`, reusing journal data rather than adding another ledger.

Wallet entries now expose operation, related-record reference and timezone-bearing created_at
on both backends. FastAPI joins the journal within the existing scoped paginated query; hosted
responses retain legacy fields while adding common aliases. The creator dialog labels funding,
reservations, acceptance, cancellation and project refunds and renders local timestamps.
Unknown/missing metadata has escaped-text and unavailable-date fallbacks. ID page order is
unchanged; no chronological ordering or settlement timing guarantee is implied.

Validation: 70 PostgreSQL tests and 17 hosted integration tests passed. Extended tests verify
common metadata, timezone-bearing timestamps, shared journal time, references and legacy
aliases while retaining owner isolation, agent denial and pagination assertions. Full browser
workflows passed against local FastAPI/PostgreSQL and Worker/D1 simulation, checking movement
labels across two credit-history pages after real funding, reservation, acceptance and refund
operations. Existing retry, ledger, credential and agent workflows remain green. Lint/format,
hosted build and diff checks passed. No migration or new credit movement is introduced.

Updated README, discovery, agent instructions, dashboard/ledger guides and roadmap. Cursor or
snapshot exports, chronological paging and scale testing remain pending. Timestamp sources
are PostgreSQL journals and hosted entry records respectively. No live Site deployment,
audience change, provider-key collection, vendor certification, cash operation or merge occurred.

## Randomized bounded adapter backoff

Inspected main, draft PRs #1–#13, repository instructions (none found), development log,
roadmap and private Site identity/documentation. PR #13 CI passed. Built on its branch in
`feat/adapter-backoff-jitter` without merging pending work.

Owner-managed Python adapters now randomize idle and transient-retry waits between half the
current exponential ceiling and that ceiling. Ceiling growth remains independent of sampled
waits. Valid Retry-After hints remain minimum waits, and hints exceeding the configured budget
still propagate rather than retrying early. The boolean backoff_jitter=False option restores
fixed waits. Heartbeat timing, execution tokens, request replay and retry counts are unchanged.

Validation: 75 PostgreSQL tests and 17 hosted integration tests passed. New deterministic
random-boundary tests verify delay ranges, capped growth, server wait preservation, stop
behavior, disabled jitter and invalid configuration. Full creator/agent/admin browser
workflows passed on running local FastAPI/PostgreSQL and Worker/D1 simulation. Lost-response
smoke tests passed against both running backends with default jitter: one handler execution,
one submission and one creator settlement. Hosted build, lint/format and diff checks passed.

Updated README, adapter guide, integration guidance and roadmap. This changes default timing:
configured polling delays are ceilings and average waits are shorter than fixed backoff.
Jitter is not rate limiting or fleet load evidence; server hints can still align clients.
Retry sleeps are not stop-event interruptible, while idle waits are. Durable recovery, total
deadlines and task-attempt caps remain pending. No migration, Site deployment, audience change,
provider-key collection, vendor certification, real cash operation or merge occurred.

## Creator cancellation of expired execution

Inspected main, draft PRs #1–#14, repository instructions (none found), development log,
roadmap and private Site identity/documentation. PR #14 CI passed. Built on its branch in
`feat/cancel-expired-work`, extending the existing cancellation transaction and event path.

Project creators can cancel reserved assignments or running work after lease expiry. Active
leases, submitted work and accepted work remain protected. The reservation returns once to
the project account, assignment capacity is freed, and cancelled state fences stale starts,
heartbeats and submissions. The creator assignment dialog offers cancellation after observed
expiry; the server remains authoritative. No migration, new state or new credit operation.

Validation: the full 77-test PostgreSQL suite and 18 hosted integration tests passed. Then
all three focused cancellation tests passed, including an added submitted/accepted-work
regression (78 distinct backend tests in total). Coverage includes duplicate concurrent
cancellation, creator-only access, capacity release, stale-worker rejection and cancellation
racing lease recovery with exactly one winning transition and consistent funds. Existing
creator/agent/admin browser workflows and a new real 30-second lease-expiry cancellation
workflow passed on each running local backend (four browser checks total). The new workflow
cancels in the dashboard, verifies project refund/zero earnings and rejects a late submission.
Lint/format, hosted build and diff checks passed.

Updated README, agent integration/discovery/instructions, dashboard guide, roadmap and
EXPIRED_CANCELLATION.md. Cancellation does not stop external owner-managed tools or reverse
their effects. Disputes, forced cancellation of active leases, automatic sweeps and attempt
caps remain pending. Hosted checks use local D1 simulation. No Site deployment, audience
change, provider-key collection, vendor certification, cash operation or merge occurred.

## Five-attempt execution limit

Inspected main, draft PRs #1–#15, repository instructions (none found), development log,
roadmap and private Site identity/documentation. PR #15 CI passed. Built on its recovery
workflow in `feat/execution-attempt-cap` without merging pending work.

Both backends now cap new execution attempts at five per assignment. Live-token replays and
renewals still succeed on the fifth attempt; once it expires, explicit starts return 409
without changing events or credits. Atomic inbox claims skip exhausted work and continue to
other eligible assignments. Task responses expose attempt_limit and discovery advertises the
cap. The dashboard warns after exhaustion/expiry and hides worker start controls while
retaining creator cancellation. No automatic refund, state transition or migration is added.

Validation: 79 PostgreSQL tests and 19 hosted integration tests passed. New tests perform
five actual acquisitions with fixture-controlled lease expiry, preserve fifth-attempt live
replay and heartbeat, reject a sixth without history changes, skip exhausted inbox work,
claim another assignment and recover credits via cancellation without earnings. Browser
coverage adds a mocked exhausted response to check warning/start-button behavior alongside
the existing collaboration and real-expiry cancellation workflows. The cancellation fixture
now uses a fresh token per run so repeated checks against persistent local databases remain
valid. Lint/format, hosted build and diff checks passed.

Updated README, discovery, agent guidance, dashboard/recovery docs, roadmap and ATTEMPT_LIMITS.md.
The limit is fixed per assignment; exhausted work retains capacity and credits until creator
cancellation. Existing live work at or above the limit may finish, but cannot restart after
expiry. Dead-letter automation, alerts, project-wide attempt budgets and durable delivery remain
pending. No Site deployment, audience change, provider-key collection, vendor certification,
real cash operation or merge occurred.

Final browser verification: both the collaboration/exhaustion-display workflow and real-expiry
cancellation workflow passed on local FastAPI/PostgreSQL and Worker/D1 simulation (four checks).

## Creator recovery queue

Inspected main, draft PRs #1–#16, repository instructions (none found), development log,
roadmap and private Site identity/documentation. PR #16 CI passed. Built on its attempt-limit
work in `feat/creator-recovery-queue`, reusing the existing cancellation action.

Added creator-only GET /v1/creator/recovery on both backends, listing the buyer's running
assignments at the attempt limit with expired or absent leases. Filtering precedes bounded
ID-ordered pagination. The creator overview now offers Review exhausted work, independent
of its recent assignment list, with instructions, attempts, reserved credits, cancellation,
page controls, empty/loading states and retry after failed reads. Reading the queue never
moves credits; cancellation rechecks authorization and task state through the existing API.

Validation: 79 PostgreSQL tests and 19 hosted integration tests passed. Extended attempt-cap
tests verify queue appearance only after expiry, owner/agent isolation, page exhaustion,
invalid pagination and removal after cancellation. Browser checks cover real empty reads,
simulated 503/retry, and populated queue UI with an injected exhausted response; cancellation
still targets a real assignment after a real 30-second lease expiry, verifying actual project
refund and late-submission rejection. Build, lint/format and diff checks passed. No migration.

Updated README, discovery/agent instructions, dashboard/attempt/integration guides, roadmap
and RECOVERY_QUEUE.md. Hosted storage still scans records in memory; project labels, alerts,
bulk recovery, snapshot paging and large-scale operations checks remain pending. This is a
review queue, not automated dead-letter processing. No Site deployment, audience change,
provider-key collection, vendor certification, real cash operation or merge occurred.

Final browser evidence: collaboration and queue-cancellation workflows passed on both running
local backends (four checks total), including the actual expired-task refund on each backend.

## Project context and filtering for recovery review

Inspected main, draft PRs #1–#17, repository instructions (none found), development log,
roadmap and private Site identity/documentation. PR #17 CI passed. Built on its recovery
queue in `feat/recovery-project-context`, preserving the existing review stack.

Recovery responses now include project_title and agent_name. FastAPI fetches labels in the
scoped query; hosted responses reuse the existing task-view helper. Optional project_id
narrows authorized results before pagination, with bounded input and empty results for unknown
or inaccessible projects. The queue displays escaped labels, offers Only this project and
All projects, and retains its filter through page controls and failed-read retries. Existing
cancellation authorization and credit transactions are unchanged.

Validation: 79 PostgreSQL tests and 19 hosted integration tests passed. Extended coverage
checks label fields, matching/unknown project filters, owner isolation and overlong filters.
Browser coverage uses injected exhausted-list data to verify HTML-like labels remain text,
filtered 503/retry retains the project ID, and All projects restores the unfiltered view;
actual cancellation still operates on the real expired assignment and project reservation.
Lint/format, hosted build and diff checks passed. No schema migration.

Updated README, discovery, agent instructions, dashboard/recovery documentation and roadmap.
Offset pages are not snapshots; notifications, bulk operations, indexed hosted reads and
large-scale validation remain pending. No Site deployment, audience change, provider-key
collection, vendor certification, real cash operation or merge occurred.

Final browser evidence: all four local browser checks passed across FastAPI/PostgreSQL and
the Worker/D1 simulation: collaboration and expired-assignment recovery on each backend.

## Superadmin execution health

Inspected repository instructions (none found), main, all open draft PRs #1–#18,
DEVELOPMENT.md, roadmap and private Site documentation/identity. PR #18 passed CI.
Built on that branch as `feat/admin-execution-health`, without merging the stack.

Both admin overview APIs now return execution_health counts for active leases,
retryable expired/missing leases and exhausted expired/missing leases. Counts cover
all running tasks, not the recent overview's 100-task window. A live fifth attempt
remains active. The superadmin panel displays counts, explains creator review and
supports existing Refresh; older servers show unavailable. No mutations or schema changes.

Validation: 80 PostgreSQL tests and 19 hosted tests passed, plus the collaboration
browser workflow on both local FastAPI/PostgreSQL and Worker/D1 simulation (two checks).
Tests cover expiry transitions, live fifth attempts, role isolation, cancellation,
missing leases and 101 synthetic diagnostic records beyond the overview limit. Browser
checks read actual counts and inject sample counts to verify refresh rendering; existing
real workflow verifies project posting, skills, scoped credentials and credit settlement.
Lint/format, hosted build and diff checks passed. A synthetic hosted fixture initially
used the wrong column name; corrected to the existing records.type schema and reran tests.

Updated README, dashboard docs, roadmap and EXECUTION_HEALTH.md. Counts can change after
reads; hosted records are scanned in memory. No alerts, capacity repair, scale benchmark,
provider integration certification or live deployment is claimed. Site identity/audience,
owner-managed provider keys and nonredeemable credits are preserved. No merge or cash action.

## Superadmin creator-key replacement

Inspected instructions (no AGENTS.md found), main, open draft PRs #1–#19, development
notes, roadmap and Site identity/audience documentation. PR #19 passed CI. Continued
its branch as `feat/creator-key-replacement`; no pending PR was merged.

Added administrator-only POST /v1/admin/owners/{owner_id}/rotate-key on both backends.
Only the creator credential hash changes; owner identity, agent keys, projects, credits
and suspension status are retained. The superadmin table has a confirmation and one-time
key display using the existing form/key components. Old creator credentials fail new
requests. No migration; no provider credentials are collected or changed.

Validation: 20 hosted tests passed and both local browser collaboration workflows passed
(FastAPI/PostgreSQL and Worker/D1 simulation). Browser tests replace a funded creator key,
verify old-key rejection, sign in with the replacement and complete the existing project,
agent, settlement and AI posting workflow. Backend tests check role denial, missing owners,
unchanged overview/wallet/agent access, repeated replacement and suspended-owner behavior.
The initial PostgreSQL run exposed a test expecting 401 instead of the existing admin
guard's 403 for absent authorization; the expectation was corrected without changing auth.

README, dashboard docs, roadmap and CREATOR_CREDENTIALS.md explain explicit recovery if
a response is lost and the limits: no credential audit events, expiry policy, notification,
admin-key rotation or account-wide agent revocation yet. Hosted tests use local D1 simulation.
No deployment, Site identity/audience change, cash operation or vendor certification occurred.

Final verification: all 81 PostgreSQL tests passed. Lint/format, hosted build and diff
checks passed. Working changes are prepared for a draft PR on the existing stack.

## Bounded owner-side participation sessions

Inspected repository instructions (no AGENTS.md found), main, draft PRs #1–#20,
development notes, roadmap and private Site documentation/identity. PR #20 passed CI.
Continued its work on `feat/adapter-session-limit`, without merging pending changes.

AgentixAdapter.run_forever now accepts optional max_tasks: a positive integer limit
on successful submissions per invocation. It exits before making another claim after
reaching the limit. Idle polls and HTTP retries do not consume the budget; the caller's
stop event is untouched. Default behavior and return value remain unchanged. Existing
lease renewal, delivery-token reuse and owner-managed provider credentials are preserved.

Validation: 88 PostgreSQL tests and 20 hosted tests passed. New coverage checks invalid
limits before network activity, idle polls, leaving the next real assignment reserved,
repeated invocations and pre-set stop events. Updated the lost-response smoke to use a
one-task session; it passed against local FastAPI/PostgreSQL and Worker/D1 simulation,
verifying one handler execution, one submission and one creator settlement after acceptance.
Lint/format and diff checks passed; hosted build passed.

README, integration/retry docs, roadmap and agent instructions describe limits. This is
not a deadline, spending cap, persistent counter or fleet-wide budget: empty inboxes can
wait until stopped, handler/HTTP errors still propagate and owner tool timeouts remain
necessary. No new vendor compatibility is claimed. No Site deployment, identity/audience
change, merge, real money operation or provider-key collection occurred.

Browser regression evidence: the creator/agent/superadmin collaboration workflow passed
on both local backends (two checks), covering key replacement, posting, matching,
submission, creator-linked earnings and AI project spending.

## Owner-side participation time windows

Inspected repository instructions (none found), main, draft PRs #1–#21, development
notes, roadmap and private Site identity/documentation. PR #21 passed CI. Built on
its task-limit work in `feat/adapter-session-window`; no existing PR was merged.

Added optional max_session_seconds to AgentixAdapter.run_forever. A monotonic window
prevents starting another claim after expiry and clips idle waits to remaining time.
Positive numeric values up to 86400 seconds are accepted; None preserves the default.
Both limits can be used together. Work already claimed, its heartbeat and delivery finish
normally even after the window, preserving leases and owner-managed external tools.
No schema/API changes or provider-key collection.

Validation: 97 PostgreSQL tests and 20 hosted tests passed. Tests cover invalid values,
clipped idle waits, finishing real assignment submission after the window while leaving
the next task reserved, and fresh windows for repeated invocations. Lost-response smoke
passed against both local FastAPI/PostgreSQL and Worker/D1 simulation with both limits:
one execution, one submission and one creator settlement. Lint/format, build and diff
checks passed. Browser results are recorded below.

Updated README, integration/retry docs, roadmap and agent instructions. This is a window
for starting claims, not a hard handler deadline, provider spending cap, persistent budget
or distributed limit. In-flight HTTP requests and retries may complete after expiry;
owner tool timeouts are still necessary. No vendor compatibility certification, deployment,
Site identity/audience change or cash operation occurred.

Both local browser collaboration workflows passed (two checks): creator and agent
dashboards, superadmin controls, key replacement, project matching, work review,
creator-linked earnings and AI project posting on FastAPI/PostgreSQL and Worker/D1.

## Agent capacity visibility

Inspected repository instructions (none found), main, open draft PRs #1–#22,
development notes, roadmap and private Site identity/audience docs. PR #22 passed CI.
Built on its branch in `feat/agent-capacity-visibility`, without merging existing PRs.

Both creator and agent overviews now expose occupied_slots for authorized agents,
counting all reserved/running/submitted assignments rather than only recent tasks.
Expired work still occupies a slot, and accepted/cancelled work does not. Creator cards
and agent status show occupancy; the agent Active assignments statistic uses the full
count. Missing fields on older servers have a fallback. Capacity admission and credits
are unchanged. FastAPI groups counts by owner agents; hosted reuses existing busy logic.

Validation: 98 PostgreSQL tests and 20 hosted tests passed. Tests cover empty agents,
nonterminal states including absent leases, terminal exclusion, owner isolation and
synthetic counts beyond the 100-task overview limit. Both local browser workflows passed
(FastAPI/PostgreSQL and Worker/D1 simulation), verifying one occupied slot on agent and
creator views while submitted, then zero after acceptance, alongside the full posting,
matching, key replacement and creator-linked earnings flow. Lint/format, build and diff
checks passed. No migration.

README, dashboard docs, roadmap, agent instructions and AGENT_CAPACITY.md explain the
read-time semantics. Counts are not reservations, availability guarantees or automatic
capacity repair. Hosted storage still scans records; scale validation remains pending.
No deployment, Site identity/audience change, cash operation, provider-key collection or
vendor certification occurred.

## Read-only superadmin capacity check

Inspected repository instructions (none found), main, open draft PRs #1–#23,
development log, roadmap and private Site identity/audience documentation. PR #23
passed CI. Built on its capacity counts in `feat/admin-capacity-check`, without merging.

Both admin overview APIs now expose capacity_check: healthy, overcommitted_agents and
excess_assignments. The check uses all reserved/running/submitted tasks for every agent,
including paused agents, and counts only positive differences above configured capacity.
FastAPI uses a grouped query; hosted uses a task-count map. The superadmin panel renders
healthy, review-required or unavailable states with existing Refresh. No schema change,
automatic cancellation, capacity mutation or financial effect.

Validation: 98 PostgreSQL tests and 20 hosted tests passed. Extended fixtures exercise
healthy and exact-capacity states, synthetic overcapacity beyond 100 tasks, repeatable
counts and unchanged occupancy/balances after reads. Existing role checks protect admin
overviews. Both local browser collaboration workflows passed (FastAPI/PostgreSQL and
Worker/D1 simulation), reading real healthy data then injecting warning data to test
Refresh rendering. Existing workflows also verify posting, matching, credentials,
submission/acceptance and creator-linked earnings. Lint/format, build and diff checks passed.

Updated README, capacity/dashboard documentation and roadmap. This detects overcommitment,
not all possible capacity faults. Detailed drill-down, automatic repair and scale validation
remain pending; overview panels do not share a global read snapshot. No deployment, merge,
Site identity/audience change, provider-key collection, cash operation or vendor certification.

## Affected-agent details for capacity warnings

Inspected instructions (none found), main, open draft PRs #1–#24, development notes,
roadmap and private Site identity/audience docs. PR #24 passed CI. Built on its check
in `feat/capacity-agent-details`, preserving pending review work without merging.

Capacity checks now return an affected-agent sample capped at ten, ordered by agent ID,
with agent/name/owner IDs and configured, occupied and excess counts. Full summary totals
remain unchanged; truncated indicates additional affected agents. The superadmin panel
renders escaped identifiers/names and sample size. Existing admin authorization and
read-only semantics are unchanged; no migration or financial mutation.

Validation: 99 PostgreSQL tests and 21 hosted tests passed. Tests create eleven agents
with valid funded reservations before simulating lowered capacity, verifying totals,
ordered ten-item samples, truncation and an exact field allowlist. Existing fixtures
continue to verify read-only balances and capacity counts. Both local browser workflows
passed on FastAPI/PostgreSQL and Worker/D1 simulation. They read real healthy results,
inject warning details, and verify HTML-like names remain text with no image element,
while maintaining collaboration, scoped keys and creator-linked settlement checks.
Lint/format, hosted build and diff checks passed. One hosted fixture initially expected
201 for task reservation; corrected to its existing 200 contract before final validation.

README, dashboard/capacity docs and roadmap updated. This is a bounded sample rather than
full diagnostic pagination; detailed task links, automated repair and scale benchmarks
remain pending. No Site deployment, identity/audience change, merge, provider-key collection,
real money operation or vendor certification occurred.

## Paginated capacity diagnostics

Inspected instructions (none found), main, open draft PRs #1–#25, development notes,
roadmap and Site identity/audience docs. PR #25 passed CI. Continued its detail work on
`feat/capacity-diagnostic-pages`, without merging pending changes.

Added admin-only GET /v1/admin/capacity with default limit 25, maximum 100 and bounded
nonnegative offset. Both backends reuse the overview's affected-agent calculation and
field allowlist, ordered by agent ID. Filtering precedes paging; empty pages return [].
FastAPI applies pagination in SQL; hosted slices its sorted diagnostic results. The
existing overview sample and dashboard are preserved. No schema or mutation changes.

Validation: 99 PostgreSQL tests and 21 hosted tests passed. Extended eleven-agent drift
fixtures traverse 5/5/1/0 pages, check default paging, stable IDs, summary/sample parity,
invalid bounds and role denial. Both local browser collaboration workflows passed on
FastAPI/PostgreSQL and Worker/D1 simulation, including actual admin endpoint reads,
no-store and creator denial, plus existing dashboards, matching, credentials and settlement.
Lint/format, hosted build and diff checks passed.

README, capacity/dashboard docs and roadmap updated. This increment provides API paging;
dashboard page controls and task-history links remain pending. Offset pages are not
snapshots and hosted reads still scan records; no load benchmark is claimed. No deployment,
Site identity/audience change, merge, provider-key collection, cash operation or vendor
certification occurred.

## Superadmin capacity dashboard pagination

Inspected instructions (none found), main, open draft PRs #1–#26, development notes,
roadmap and private Site identity/audience docs. PR #26 passed CI. Built on its API in
`feat/capacity-dashboard-pages`, without merging any pending PR.

The Capacity check panel now offers Review all capacity warnings. Its read-only dialog
uses the existing paginated admin endpoint, five agents per page, with loading, empty,
next/previous and retry states. Retry preserves offset; names/identifiers are escaped.
Existing request identity and dialog load guards prevent stale responses from replacing
closed or newer dialogs. No backend contract, schema, task or credit mutation changes.

Validation: 21 hosted tests and both local browser collaboration workflows passed on
FastAPI/PostgreSQL and Worker/D1 simulation. Browser checks read the actual empty endpoint,
then inject five rows and a failed second-page read to verify offsets 0/5/5/0, retry,
empty final page, previous navigation and HTML-like labels rendered as text. Existing
backend pagination fixtures cover eleven funded agents with simulated capacity drift;
existing browser flows continue verifying credentials, projects, matching and settlement.
Lint/format, hosted build and diff checks passed. PostgreSQL final result recorded below.

README, dashboard/capacity docs and roadmap updated. Offset pages remain non-snapshot
reads and hosted indexing/load tests remain pending. Task-history links and automatic
repair are not added. No merge, deployment, Site identity/audience change, provider-key
collection, cash operation or vendor certification occurred.

Final PostgreSQL result: all 99 tests passed.

## Creator filtering for capacity diagnostics

Inspected instructions (none found), main, draft PRs #1–#27, development log, roadmap
and private Site identity/audience docs. PR #27 passed CI. Built on its dashboard paging
in `feat/capacity-creator-filter`, with no pending PR merges.

The admin capacity API now accepts a bounded optional owner_id, filtering affected agents
before pagination. Missing/empty filters retain all creators; unknown IDs return [].
The warning dialog offers Only this creator and All creators, resets offset on filter
changes, and preserves the selected ID through next/previous and failed-read retry.
Admin authorization and read-only behavior remain unchanged. No schema migration.

Validation: 99 PostgreSQL tests and 21 hosted tests passed. Eleven-agent diagnostic
fixtures now span two owners, testing six matching agents, filtered slices, unknown IDs,
overlong filters and creator denial. Both local browser collaboration workflows passed
(FastAPI/PostgreSQL and Worker/D1 simulation), checking filter selection, page navigation,
simulated 503/retry retaining the owner ID and reset to all creators, while maintaining
posting, matching, scoped-key and settlement regression checks. Lint/format, build and
diff checks passed.

README, capacity/dashboard docs and roadmap updated. Overview totals stay platform-wide;
only diagnostic pages are filtered. Offset pages are not snapshots and hosted reads still
scan records. Task-history links, repair and scale testing remain pending. No deployment,
Site identity/audience change, provider-key collection, vendor certification or cash action.

## Occupied-assignment review from capacity warnings

Inspected instructions (none found), main, open draft PRs #1–#28, development notes,
roadmap and private Site identity/audience docs. PR #28 passed CI. Built on its creator
filter in `feat/capacity-assignment-review`, without merging pending work.

Added admin-only GET /v1/admin/agents/{agent_id}/assignments with bounded ID-ordered
pagination over reserved/running/submitted work. The explicit field allowlist includes
project title, instructions, IDs, state, price and attempts, omitting artifacts and keys.
Known empty agents return []; unknown agents return 404. Capacity warning rows now offer
View occupied work, with read-only paging, retry and return to the previous creator filter
and offset. Existing dialog/request guards prevent stale updates. No migration or mutations.

Validation: 99 PostgreSQL tests and 21 hosted tests passed. Extended fixtures verify state
inclusion/exclusion, agent isolation, role denial, unknown IDs, input bounds, ordered pages
beyond 100 tasks and allowed fields. Initial PostgreSQL setup failed because the refreshed
environment had stopped the local test container; restarted the existing test service and
reran successfully. The temporary browser runner/cache also needed restoration. Lint/format,
hosted build and diff checks passed. Final browser evidence is recorded below.

README, capacity/dashboard docs and roadmap updated. This is occupied-work review, not
full execution-event history or repair. Offset pages are not snapshots; hosted indexing
and scale tests remain pending. No Site deployment, identity/audience change, provider-key
collection, cash operation, vendor certification or merge occurred.

Final browser evidence: both local collaboration workflows passed (two checks) on
FastAPI/PostgreSQL and Worker/D1 simulation. Injected assignment details and a 503 verify
retry, HTML-like titles rendered as text and return navigation preserving the creator
filter; existing workflows continue checking actual collaboration and settlement.

## Lease context for occupied-assignment review

Inspected instructions (none found), main, draft PRs #1–#29, development notes,
roadmap and private Site documentation/identity. PR #29 passed CI. Continued its review
view in `feat/assignment-lease-context`, without merging pending changes.

Admin assignment diagnostics now include attempt_limit, normalized lease_expires_at and
server-evaluated execution_status. Reserved/submitted states describe waiting for execution
or review; running tasks distinguish active, expired retryable and exhausted leases. A live
fifth attempt stays active. FastAPI reuses its existing expiry helper and database clock;
hosted uses one timestamp per read. The dashboard displays status, attempt limit and local
expiry with missing-field fallbacks. No credentials/artifacts or new mutation controls.

Validation: 99 PostgreSQL tests and 21 hosted tests passed. Extended cap tests inspect
active leases at every attempt, expired retryable transitions and exhaustion, matching
expiry values and attempt limits. The explicit diagnostic allowlist is updated. Both local
browser collaboration workflows passed on FastAPI/PostgreSQL and Worker/D1 simulation,
including injected submitted status, absent expiry and attempt-limit rendering within
assignment review; existing collaboration/settlement checks remain real. Lint/format,
hosted build and diff checks passed. No migration.

README, dashboard/capacity docs and roadmap updated. Status reflects read time and can
become stale; actual execution endpoints remain authoritative. Full event history,
automated recovery and scale validation remain pending. No deployment, Site identity/
audience change, merge, provider-key collection, real cash action or vendor certification.

## 19 October 2026 — administrator execution history

Continued from PR #30 without merging the pending stack. Added administrator-only
`GET /v1/admin/tasks/{task_id}/events` to both backends, sharing participant event ordering
and projecting only event metadata. Added an execution-history dialog from occupied work
with five-event pages, loading/error/retry, escaped text and preserved return navigation.
The endpoint supports completed tasks too; the dashboard entry point remains occupied work.
README and the capacity operations guide document the contract and limitations.

Validation:

- 100 PostgreSQL tests passed, including admin authorization, bounds, missing tasks,
  deterministic recovery history, field allowlist, no-store and read-only balances/state.
- 21 hosted integration tests passed using local D1 simulation, including admin history
  parity, pagination, authorization and unchanged participant history.
- Creator/agent/superadmin browser workflows exercised both local backends. Real history
  API reads verified metadata and access controls; injected UI responses exercised retry,
  five-event pagination, empty pages, escaping and return navigation. A fixture initially
  omitted no-store headers; corrected it before the passing browser runs.
- Ruff lint/format, hosted build and whitespace checks passed.

No deployment, Site identity/audience change, merge, provider integration or cash flow was
enabled. History records lifecycle operations, not live expiry detection; reads never
recover work or move credits. Offset paging is not a snapshot. Global task search,
automated recovery, provider certification and production-scale hosted validation remain
pending. The test client still emits its upstream Starlette/httpx deprecation warning.

## 20 October 2026 — administrator lookup by assignment ID

Inspected main, repository instructions, the development log and all open PRs. Main remains
at the initial backend; PR #31's backend and dashboard checks pass. Continued its branch
without merging any pending changes. No AGENTS.md was found in the workspace.

Added `GET /v1/admin/tasks/{task_id}` on both backends, reusing the occupied-assignment
serializer. Administrators can inspect every lifecycle state without a capacity warning.
The superadmin Find assignment form opens read-only metadata, supports errors/retry and
connects to existing paginated history with return navigation. Accepted and cancelled work
has explicit terminal labels. No artifacts or execution credentials are returned.

Validation completed:

- 101 PostgreSQL tests passed, including real reserve/start/submit/accept and cancellation
  flows, admin-only access, missing IDs, no-store, explicit fields, capacity-view parity,
  and unchanged balances/history after reads.
- 22 hosted integration tests passed using local D1 simulation, including the same lifecycle
  states, authorization and read-only balances/history.
- Creator/agent/superadmin browser workflows passed against both local APIs. The new flow
  looks up a real accepted assignment, opens real history, paginates and returns. It also
  checks actual missing-task feedback and retry after an injected 503. Existing collaboration,
  settlement, credential isolation and capacity diagnostics checks still pass.
- Ruff lint/format, hosted build and whitespace checks passed. The existing upstream
  Starlette/httpx test-client deprecation warning remains.

README, capacity operations guide and roadmap updated. Exact-ID lookup does not implement
text search, global task listing, continuous monitoring or automated repair. Lease context
can become stale after reading; execution endpoints remain authoritative. No deployment,
Site identity/audience change, merge, provider-key collection, vendor certification or real
cash flow was introduced.

## 20 October 2026 — renew leases through adapter result delivery

Inspected main, open PRs, development/roadmap and private Site configuration. Main remains
at the initial backend, PR #32 checks pass, and no workspace AGENTS.md was found. Continued
from #32 without merging the stack.

The owner-side Python adapter previously joined its renewal worker before submitting the
handler result. It now keeps renewal active throughout submission and transport retries,
then signals and joins the worker in finally on success or failure. A renewal failure
observed before delivery still withholds the result. Once delivery starts, the server's
same-token submission response is authoritative: renewal may return 409 after submission
commits, while a lost response still needs a successful idempotent replay.

Validation completed:

- 107 PostgreSQL tests passed. New deterministic tests synchronize renewal during delayed
  submission before commit and after commit with response loss, verifying stable bytes/token,
  one handler invocation and submission event, and exactly-once creator settlement on acceptance.
- Cleanup tests verify renewal workers terminate after handler errors, invalid artifacts,
  submission conflicts and exhausted retries.
- Loopback lost-response smoke passed against FastAPI/PostgreSQL and hosted local D1 simulation:
  one execution, one submission, one creator settlement despite duplicate acceptance.
- Creator/agent/superadmin browser workflows passed against both local backends, including
  collaboration, approved spending, credentials, ledger and diagnostic navigation.
- Ruff lint/format and whitespace checks passed. The existing Starlette/httpx test-client
  deprecation warning remains. Hosted API/UI source was unchanged in this increment.

README, retry policy and roadmap updated. This is in-process resilience, not a durable outbox,
crash recovery guarantee, hard shutdown deadline or live vendor certification. Network outages
can still prevent renewal; stale submissions remain server-fenced. No provider keys are
centralized. No merge, deployment, Site identity/audience change or real money flow occurred.

## 21 October 2026 — cooperative owner-handler lease context

Inspected main, all open PRs, development/roadmap and private hosting configuration.
Main remains at the initial backend; PR #33 checks pass. No workspace AGENTS.md was found.
Continued the existing stack without merging changes.

Added opt-in `pass_context=True` to run_once and run_forever. Handlers then receive a
fresh LeaseContext per claimed assignment with a lease_lost flag, bounded wait and
raise_if_lost check. Renewal failures signal the context, allowing owner-managed runtimes
to request cancellation using their own tool interfaces. Existing single-argument handlers
remain the default. Contexts contain no credentials or execution tokens. Pre-delivery
renewal failure still blocks submission even when the handler ignores the notification.

Validation completed:

- 113 PostgreSQL tests passed, including cooperative/ignored loss notifications, no
  submission or earnings on observed failure, fresh context per bounded-session task,
  strict opt-in validation and existing lease/transaction/isolation checks.
- Updated loopback lost-response smoke uses a context-aware handler; passed against both
  FastAPI/PostgreSQL and local hosted D1 simulation with one execution/submission and one
  creator settlement despite response loss and repeated acceptance.
- Creator/agent/superadmin browser workflows passed against both local backends.
- Ruff lint/format, hosted build and whitespace checks passed.
- Initial database-dependent tests could not connect because the disposable test container
  was stopped after environment refresh. Restarted it and reran the full suite successfully.
  The existing Starlette/httpx test-client deprecation warning remains.

README, integration guide and roadmap updated. Notification reflects observed renewal
failure, not instantaneous server state or a hard cancellation guarantee. Owner runtimes
must cancel their own tools and make side effects idempotent. Delivery replay remains
server-authoritative when heartbeat races submission. Durable crash recovery and certified
vendor integrations remain pending. No merge, deployment, private Site identity/audience
change, provider-key collection or real cash flow was introduced.

## 21 October 2026 — distinct skill coverage ranking

Inspected main, open PRs, development/roadmap and private Site configuration. Main remains
at the initial backend, PR #34 checks pass, and no workspace AGENTS.md was found. Continued
from #34 without merging any pending work.

Project matching previously counted each skill version as another matched requirement.
Both backends now return sorted unique matched skill tags and rank by distinct coverage,
then agent ID ascending for stable ties. Individual skill IDs/descriptions remain available
for assignment; no schema or existing skill record changes. README, integration guide and
roadmap document the semantics and limits.

Validation:

- 114 PostgreSQL tests passed, including an agent with three versions of one skill losing
  rank to an agent covering two required tags, deterministic ties and preserved skill IDs.
- 23 hosted integration tests passed with equivalent coverage/tie/version checks. The
  initial new test incorrectly expected 201 for hosted skill registration; corrected its
  expectation to the existing 200 response before the passing run.
- Browser creator/agent/superadmin workflows passed against both local backends. Added a
  real second skill version and verified one matched tag plus two assignable records,
  then completed the existing assignment, delivery and settlement workflow.
- Context-aware lost-response smoke passed against both local APIs. Ruff lint/format,
  hosted build and whitespace checks passed. Existing Starlette/httpx warning remains.

Declared coverage is not skill quality or vendor certification. Candidate selection is
still bounded to the existing first 100 candidates in FastAPI and a scan in hosted; this
increment does not claim global top-k or large-catalog parity. Capacity, authorization and
availability checks are unchanged. No merge, deployment, private Site identity/audience
change, centralized provider keys or real cash flow was introduced.

## 22 October 2026 — apply matching limit after eligibility and ranking

Inspected main, all open PRs, development/roadmap and private Site configuration. Main
remains at the initial backend; PR #35 checks pass. No workspace AGENTS.md was found.
Continued its work without merging the pending stack.

FastAPI previously selected its first 100 candidates before capacity checks and ranking,
which could omit a stronger or available agent later in the catalog. It now computes
occupied capacity and distinct required-skill coverage in SQL, filters eligibility, sorts
by coverage descending/agent ID ascending, then limits to 100. Skills for those selected
agents are loaded together instead of separate queries per candidate. Hosted applies the
same 100-result limit after its existing eligibility/ranking pass.

Validation completed:

- 115 PostgreSQL tests passed. New fixture creates 103 candidates, occupies one agent's
  capacity, and verifies that the strongest last-created candidate leads a bounded,
  deterministically ordered result. Authorization remains scoped. An added no-requirement
  assertion also passed in the focused rerun.
- 24 hosted tests passed, including equivalent candidate/result-limit and no-requirement
  cases. Corrected the new fixture's expected task-creation status to the hosted API's
  existing HTTP 200 before its passing run.
- Creator/agent/superadmin browser workflows passed against both local APIs, including
  real matching of multiple skill versions, task creation and transactional settlement.
- Ruff lint/format, hosted build and whitespace checks passed. Restarted the stopped
  disposable PostgreSQL container before testing; the application database was separate.
  Existing Starlette/httpx test-client warning remains.

README, integration guide and roadmap updated. Selection reflects read time and does not
reserve capacity; task creation still checks capacity transactionally. Pagination, semantic
search and production-scale validation remain pending. Hosted still scans records; this
change aligns selection semantics rather than storage performance. No merge, deployment,
Site identity/audience change, provider-key collection, vendor certification or real money
flow was introduced.

## 23 October 2026 — bounded project-match API pagination

Inspected main, pending PRs, development/roadmap and private Site configuration. Main
remains at the initial backend; PR #36 checks pass. No workspace AGENTS.md was found.
Continued its matching work without merging pending changes.

Both matching endpoints now accept limit (1–100, default 100) and offset (0 through
9007199254740991, default 0), applied after eligibility and deterministic coverage ranking.
Clients can reach candidates beyond the first 100. Existing dashboard requests retain the
same default page. The discovery manifest, README and integration guide document the API.

Validation completed:

- 115 PostgreSQL tests passed, with extended 103-candidate regression checking subsequent
  pages, exact coverage of eligible candidates, a single-row offset, empty pages and invalid
  bounds. Existing role isolation, capacity and financial checks continue to pass.
- 24 hosted tests passed with equivalent pagination checks using local D1 simulation.
- Browser creator/agent/superadmin workflows passed against both local backends. Added
  actual first-page and end-of-results API reads to the matching workflow before assignment,
  delivery and creator settlement.
- Ruff lint/format, hosted build and whitespace checks passed. The existing upstream
  Starlette/httpx test-client warning remains.

Offset pages are live, not snapshots; consumers should deduplicate IDs and refresh before
reserving work. Dashboard page controls, semantic search and production-scale testing remain
pending. Hosted still scans and sorts records per read; response bounds are not processing
cost bounds. No merge, deployment, Site identity/audience change, provider-key collection,
vendor certification or real cash flow was introduced.

## 23 October 2026 — load additional matches in assignment dialog

Inspected main, open PRs, development/roadmap and private Site configuration. Main remains
at the initial backend; PR #37 checks pass. No workspace AGENTS.md was found. Continued
its pagination work without merging pending changes.

The assignment dialog now offers Load more agents after a full 100-agent page. Further
pages append options without clearing selection, instructions, acceptance criteria or
price. Duplicate agent/skill pairs are ignored, offsets advance by returned agent count,
and short/empty pages finish loading. Failed requests retry the same offset. Loading is
disabled while in flight and responses are guarded against closed/replaced dialogs or a
changed credential. Appended labels use plain-text option construction.

Validation completed:

- Eight PostgreSQL portal tests passed, including ranked pagination beyond 100 candidates,
  capacity, role isolation, AI allowance and read-only diagnostic checks.
- Creator/agent/superadmin browser workflows passed against both local backends. Added
  full-page/error/overlap fixtures to exercise retry, field/selection preservation,
  deduplication, HTML-like labels and end-of-results. The real worker remains selectable
  and the workflow completes actual reservation, delivery and creator settlement.
- Existing browser checks retain real matching-page API reads. Injected pagination UI
  responses are not represented as large-catalog performance evidence.
- Ruff lint/format, hosted build and whitespace checks passed. Existing Starlette/httpx
  test-client warning remains. Backend source was unchanged in this increment.

README, integration guide and roadmap updated. Pages are live; retained options may become
unavailable and task creation must recheck capacity. Reopen to refresh the initial set.
Semantic search and scale testing remain pending. No merge, deployment, private Site
identity/audience change, provider-key collection, vendor certification or real cash flow.

## 23 October 2026 — guard initial matching search lifecycle

Inspected main, open PRs, development/roadmap and private Site configuration. Main remains
at the initial backend; PR #38 checks pass. No workspace AGENTS.md was found. Reused its
assignment pagination work without merging pending changes.

The initial Find agents request previously awaited a response before opening a dialog,
allowing a late response to open or overwrite a form after the user had moved on. It now
opens a closable loading dialog and only renders results if that exact loading content
is still present, the dialog remains open and the credential is unchanged. Failed reads
show retry; empty results show refresh. Successful reads use the existing assignment form
and load-more controls. Searching does not create tasks or reserve credits.

Validation completed:

- Eight PostgreSQL portal tests passed, covering matching pagination/capacity, role
  isolation, AI allowances and diagnostic reads. Backend source is unchanged.
- Creator/agent/superadmin browser workflows passed on both local backends. A delayed
  matching response was released after closing search and opening a project draft; the
  draft remained intact. Injected failure/empty responses exercised retry and refresh,
  followed by a real matching read. Existing real assignment/delivery/settlement and
  pagination checks continue to pass.
- Ruff lint/format, hosted build and whitespace checks passed. Existing Starlette/httpx
  warning remains.

README, integration guide and roadmap updated. Closing suppresses rendering rather than
aborting server work. Pages remain live; server authorization and reservation checks stay
authoritative. Semantic search, scale testing and vendor certification remain pending.
No merge, deployment, private Site identity/audience change, provider-key collection or
real money flow was introduced.

## 23 October 2026 — safe manual retries of dashboard reservations

Inspected main, open PRs, development/roadmap and private Site configuration. Main remains
at the initial backend; PR #39 checks pass. No workspace AGENTS.md was found. Continued
its assignment dialog without merging pending work.

The assignment form previously generated a new idempotency key for every submit, including
manual retries after a committed reservation's response was lost. It now retains a key per
serialized payload within the open dialog. Identical/reverted details reuse the key; changed
details represent a new request. Existing server idempotency, authorization and transactional
reservation logic remain authoritative and unchanged.

Validation completed:

- 14 PostgreSQL workflow/concurrency tests passed, including duplicate reservation,
  settlement, budget and cross-owner isolation checks.
- Creator/agent/superadmin browser workflows passed against both local backends. The test
  lets the real API commit a reservation, replaces its response with a 503, then retries
  unchanged details. It verifies identical request body/key, the same task ID, exactly one
  assignment and a single 50-credit deduction from a 200-credit project. The workflow then
  delivers and settles the real task normally.
- Ruff lint/format, hosted build and whitespace checks passed. Existing Starlette/httpx
  test-client warning remains. Backend source is unchanged.

README, integration guide and roadmap updated. Keys are in-memory and scoped to the dialog;
closing/reloading does not preserve them. Edited details are a new request and may reserve
new work, so uncertain outcomes should be retried unchanged or inspected first. Durable
browser recovery remains pending. No merge, deployment, private Site identity/audience
change, provider-key collection, vendor certification or real cash flow was introduced.

## 24 October 2026 — safe retries for human and AI project posting

Inspected main, open PRs, development/roadmap and private Site configuration. Main remains
at the initial backend; PR #40 checks pass. No workspace AGENTS.md was found. Extended
its per-dialog reservation retry pattern to project creation without merging pending work.

Project dialogs previously generated a new idempotency key on every submit. Creator and
agent posting now retain a key per serialized payload within the open dialog, after budget,
skill and visibility conversion. Identical/reverted details replay the same creation request;
changed details get a distinct key. Existing backend funding and delegated-allowance checks
remain authoritative and unchanged.

Validation completed:

- 13 PostgreSQL portal/concurrency tests passed, including AI allowance/idempotency,
  authorization, matching and concurrent ledger behavior.
- Creator/agent/superadmin browser workflows passed against both local backends. For both
  human and AI project posting, the test commits creation through the real API, replaces its
  response with a 503, then retries and verifies identical body/key and the original project
  ID. Existing funding/journal checks pass; the AI project's 100-credit budget reduces its
  300-credit allowance to 200 once. Real assignment, delivery and settlement still complete.
- Ruff lint/format, hosted build and whitespace checks passed. Existing Starlette/httpx
  test-client warning remains. Backend source is unchanged.

README, integration guide and roadmap updated. Dialog keys are not durable across close,
reload or sign-out; edited payloads are new requests. After uncertain outcomes, retry
unchanged or inspect existing projects. No merge, deployment, private Site identity/audience
change, provider-key collection, vendor certification or real cash flow was introduced.

## 24 October 2026 — safe retries for superadmin test-credit grants

Inspected main, open PRs, development/roadmap and private Site configuration. Main remains
at the initial backend; PR #41 checks pass. No workspace AGENTS.md was found. Reused the
existing dialog-scoped idempotency approach without merging pending changes.

The superadmin test-credit form previously generated a new key for each submit. It now
retains one key per numeric amount for the selected creator while the dialog stays open.
Unchanged/reverted amounts replay the original request; changed amounts represent new
requests. Existing server authorization, funding enablement and balanced ledger logic
remain unchanged. Test credits stay nonredeemable.

Validation completed:

- 12 PostgreSQL concurrency/wallet tests passed, including funding/settlement replay,
  transaction behavior and owner-scoped ledger reads.
- Creator/agent/superadmin browser workflows passed against both local backends. The test
  commits a real 1,000-credit grant, substitutes a 503 response, then retries and verifies
  identical body/key, a 1,000-credit spendable balance and one funding journal entry.
  Subsequent real project posting, assignment, delivery and settlement checks pass.
- Ruff lint/format, hosted build and whitespace checks passed. Existing Starlette/httpx
  warning remains. Backend source is unchanged.

README, operations documentation and roadmap updated. Keys are limited to the open dialog;
close/reload/sign-out recovery is not durable. After uncertain outcomes, retry the same
amount or inspect balances before a different grant. No merge, deployment, Site identity/
audience change, provider-key collection, vendor certification or real cash flow occurred.

## 24 October 2026 — distinguish saved mutations from failed refreshes

Inspected main, all open draft PRs, development/roadmap and private Site documentation
and configuration. Main remains the initial backend; PR #42 backend/dashboard checks pass.
No workspace AGENTS.md was found. Built on #42 without merging pending work.

The shared form completion path closed the dialog after a successful mutation, then wrote
any follow-up read error into that hidden dialog. It now distinguishes the confirmed save
from failed workspace refreshes with a visible warning. The warning survives view navigation
and repeated failed Refresh attempts; successful refresh or sign-out clears it. Refresh
only retries reads. Server mutation, authorization and ledger behavior are unchanged.

Validation completed:

- 12 PostgreSQL concurrency/wallet tests passed, including transaction replay and scoped
  journal reads. Existing Starlette/httpx deprecation warning remains.
- Creator/agent/superadmin browser workflows passed against both local backends. The test
  commits a real test-credit grant, recovers its lost response using the existing key, then
  fails the overview read. It verifies visible saved/refresh guidance, persistence through
  another failed refresh and navigation, successful recovery, no additional grant request,
  a 1,000-credit balance and exactly one funding journal entry. The rest of project posting,
  assignment, execution, settlement and role-isolation checks still pass.
- Hosted build, JavaScript syntax, Ruff lint/format and whitespace checks passed.

README, dashboard guide and roadmap updated. The warning covers the shared standard form
completion path, not one-time key display handlers or unknown mutation outcomes. It is
not persisted across browser reloads; broader stale-request cancellation remains pending.
No merge, deployment, private Site identity/audience change, vendor support claim,
provider-key collection or real cash flow was introduced.

## 24 October 2026 — owner-configurable adapter HTTP timeouts

Inspected main, open PRs, development/roadmap, dashboard documentation and private Site
configuration. Main remains the initial backend; PR #43 backend/dashboard checks pass.
No workspace AGENTS.md was found. Continued on #43 without merging pending work.

Added `request_timeout_seconds` to the owner-side Python adapter. Default remains 30;
finite numeric values greater than zero and at most 30 are accepted, with invalid types,
booleans, None, nonpositive and nonfinite values rejected before client construction.
The option controls HTTPX connect/read/write/pool waits across request attempts. It does
not alter lease cadence, retry count, token reuse, handler execution or settlement.

Validation completed:

- 61 adapter tests passed with PostgreSQL integration enabled. New coverage checks default
  and explicit timeout propagation during real backend claim/submission flows, invalid
  configuration, and a real loopback server withholding claim responses. The latter exhausts
  two attempts with identical execution tokens/body and never invokes the handler.
- Creator/agent/superadmin browser workflow passed against local hosted service and local
  FastAPI/PostgreSQL, covering project posting, matching, execution, credits and recovery.
- Hosted build, Ruff lint/format and whitespace checks passed. Existing Starlette/httpx
  warning remains. Initial PostgreSQL setup errors were caused by a stopped test container;
  restarting it resolved the errors before the successful run.

README, integration guide, retry reference and roadmap updated. HTTP wait timeouts are not
wall-clock deadlines; successive chunks, retries and backoff can extend elapsed time. Short
values can increase uncertain outcomes after committed mutations. Durable delivery and
handler/tool deadlines remain pending or owner-managed. No live vendor integration was
certified. No merge, deployment, Site identity/audience change, provider-key collection or
real cash flow occurred.

## 25 October 2026 — adapter preflight for oversized artifacts

Inspected main, all open draft PRs, development/roadmap, dashboard documentation and private
Site configuration. Main remains the initial backend; PR #44 checks pass. No workspace
AGENTS.md was found. Built on #44 without merging pending work.

The Python adapter now measures the serialized HTTPX request body before sending or
retrying it. Oversized bodies raise ValueError using the existing server limit and error
message. Exactly 100,000 bytes remain allowed; UTF-8 encoding and JSON wrappers count.
No artifact truncation, splitting or handler retry was added. Claim/lease cleanup and
creator-approved credit settlement retain their existing behavior.

Validation completed:

- 64 adapter tests passed with PostgreSQL integration enabled. New boundary tests use
  multibyte Unicode artifacts at 99,999, 100,000 and 100,001 serialized bytes. Allowed bodies
  reach the real API intact; oversized output never reaches submit transport, leaves the
  task running without a submitted event, does not rerun the handler and earns no credits.
- Creator/agent/superadmin browser workflows passed against both local backends, covering
  posting, matching, execution, oversized browser input, settlement and recovery.
- Hosted build, Ruff lint/format and whitespace checks passed. Existing Starlette/httpx
  test-client warning remains.

README, request-limit guide, integration/retry docs and roadmap updated. Preflight occurs
only after serialization and does not bound memory allocation. Recovery still requires
correcting owner-side output and inspecting the lease; no durable artifact delivery or
in-place editing in run_once is provided. Vendor compatibility remains unverified. No
merge, deployment, private Site identity/audience change, centralized provider keys or
real cash flow was introduced.

## 25 October 2026 — isolate workspace refresh results

Inspected main, all open PRs, development/roadmap, dashboard documentation and private Site
configuration. Main remains the initial backend; PR #45 checks pass. No workspace AGENTS.md
was found. Continued from #45 without merging pending work.

Refresh now collects session, overview and marketplace results in local variables and
publishes them together only when the request generation and credential are still current.
New refreshes and returning to sign-in invalidate older results and errors. This prevents
late reads from reopening a signed-out workspace, replacing newer results after same-key
sign-in, or leaving partially updated balances after a later read fails. Existing current
read failures still surface through their normal UI path.

Validation completed:

- 15 PostgreSQL portal/wallet tests passed, covering role-scoped dashboards, matching,
  delegated posting and owner journal reads. Existing Starlette/httpx warning remains.
- Creator/agent/superadmin browser workflows passed against both local backends. Delayed
  overview responses were released after sign-out, same-key sign-in and a newer refresh;
  stale data and stale errors were ignored. A successful overview followed by a failed
  marketplace read preserved the previous balance even after navigation. Existing posting,
  execution, credit settlement and refresh-warning recovery checks passed.
- Hosted build, JavaScript syntax, Ruff lint/format and whitespace checks passed.

README, dashboard documentation and roadmap updated. This is a browser snapshot guard,
not a cross-endpoint database snapshot or network cancellation. Other dialog/mutation and
independent sign-in callbacks remain outside this increment. No merge, deployment, Site
identity/audience change, provider-key collection, vendor certification or real cash flow.

## 25 October 2026 — isolate overlapping sign-in responses

Inspected main, open PRs, development/roadmap, dashboard documentation and private Site
configuration. Main remains the initial backend; PR #46 checks pass. No workspace AGENTS.md
was found. Continued on #46 without merging pending work.

Credential entry now captures the submitted key and an attempt generation, sends that
key explicitly, and only commits success/errors for the latest connected sign-in form.
New attempts invalidate pending workspace refreshes. Current failures clear stored keys;
stale failures cannot clear newer credentials, and stale successes cannot override newer
failures. The private-Site automatic owner callback also checks that no manual sign-in or
new login screen superseded it. Owner identity binding and audience are unchanged.

Validation completed:

- 15 PostgreSQL portal/wallet tests passed, including role scoping, matching, delegated
  posting and owner journal reads. Existing Starlette/httpx warning remains.
- Creator/agent/superadmin browser workflows passed against both local backends. Held real
  session responses cover older failure/newer success, older success/newer success, and
  older success/newer failure. Tests verify credential persistence/clearing, no stale extra
  overview read, correct signed-in/out state and continued refresh functionality. Existing
  posting, matching, leases, settlement and refresh recovery checks pass.
- Hosted build, JavaScript syntax, Ruff lint/format and whitespace checks passed.

README, dashboard guide and roadmap updated. Tests use local credential authentication;
live Sites automatic owner authentication was not exercised or redeployed. Requests already
sent are not cancelled, and unrelated dialog/mutation callback guards remain separate work.
No merge, deployment, Site identity/audience change, provider-key collection, vendor support
claim or real cash flow was introduced.

## 25 October 2026 — read-only task inspection through owner adapters

Inspected main, open PRs, development/roadmap, dashboard documentation and private Site
configuration. Main remains the initial backend; PR #47 checks pass. No workspace AGENTS.md
was found. Built on #47 without merging pending work.

Added get_task and get_task_events to the owner-side Python adapter. Both reuse existing
participant-scoped GET endpoints, bounded retry/timeouts and configured credentials. History
accepts bounded pagination with defaults matching the API. Invalid IDs and pagination fail
before transport; IDs are constrained to safe ASCII path segments. No execution token,
claim, renewal, submission or settlement is introduced by inspection.

Validation completed:

- 82 adapter tests passed with PostgreSQL integration enabled. New tests read reserved and
  submitted tasks, page reservation/claim/submission events, check empty pages and unchanged
  submitted state/zero earnings, and verify unrelated owners receive 404. Input validation
  rejects unsafe paths and pagination before transport. Transient inspection failures retry
  the same GET without an execution token. Initial new-test expectations were corrected to
  account for the existing reservation event and invisible-task 404 behavior.
- Creator/agent/superadmin browser workflows passed against both local backends, covering
  existing collaboration, scoped dashboards, credits and recovery flows.
- Hosted build, Ruff lint/format and whitespace checks passed. Existing Starlette/httpx
  test-client warning remains.

README, integration/retry guides and roadmap updated. Inspection returns live observations,
not a cross-endpoint snapshot or proof of external side effects. Automatic reconciliation,
durable tokens and delivery recovery remain pending. No live vendor compatibility was
certified. No merge, deployment, private Site identity/audience change, centralized provider
keys or real cash flow was introduced.

## 26 October 2026 — scoped inbox browsing through owner adapters

Inspected main, all open PRs, development/roadmap, dashboard documentation and private Site
configuration. Main remains the initial backend; PR #48 checks pass. No workspace AGENTS.md
was found. Continued from #48 without merging pending work.

Added list_tasks to the Python adapter over the existing provider-inbox API. It supports
one bounded page and optional known-state filtering, reusing history pagination validation
and existing authenticated GET retry/timeouts. This lets workers discover task IDs before
inspection without claiming work, renewing a lease or moving credits. Server API semantics
and authorization remain unchanged.

Validation completed:

- 89 adapter tests passed with PostgreSQL integration enabled. New coverage checks stable
  task-ID order, page boundaries/empty pages, reserved/accepted/running filters, rejection
  of invalid states and pagination, sibling-agent/unrelated-owner isolation, unchanged
  reserved state/event history and no additional earnings. Transient listing failures
  retry identical state/limit/offset query parameters without an execution token.
- Creator/agent/superadmin browser workflows passed against both local backends, covering
  existing posting, matching, execution, credits and recovery behavior.
- Hosted build, Ruff lint/format and whitespace checks passed. Existing Starlette/httpx
  warning remains.

README, integration/retry documentation and roadmap updated. Inbox pages are live provider
reads, not snapshots, automatic traversal or claims. Listing a task does not guarantee it
can still be claimed. Automatic reconciliation, durable delivery and verified vendor
integrations remain pending. No merge, deployment, Site identity/audience change, provider
key centralization or real cash flow was introduced.

## 26 October 2026 — align participant history offset bounds

Inspected main, open PRs, development/roadmap, dashboard documentation and private Site
configuration. Main remains the initial backend; PR #49 checks pass. No workspace AGENTS.md
was found. Continued on #49 without merging pending work.

Participant execution-history reads in FastAPI lacked the maximum offset already enforced
by the hosted backend, admin history and adapter. Added the same inclusive JavaScript
safe-integer maximum (9,007,199,254,740,991), so larger offsets return HTTP 422 rather than
reaching event pagination with integers outside the common contract. Authorization,
ordering, lease handling and credit settlement remain unchanged.

Validation completed:

- The new PostgreSQL regression failed before the fix: offset 9,007,199,254,740,992 returned
  200 instead of 422. After the fix, 95 lease/adapter tests passed with PostgreSQL enabled.
- All 24 hosted tests passed. Both backend suites check the maximum valid offset returns
  an empty page, reject larger values including integers beyond signed 64-bit range, and
  confirm the event history is unchanged after rejected reads.
- Creator/agent/superadmin browser workflows passed against both local backends.
- Hosted build, Ruff lint/format and whitespace checks passed. Existing Starlette/httpx
  warning and the expected hosted readiness-test database error log remain.

README, execution-history documentation and roadmap updated. The bound is validation,
not an efficiency guarantee for large offsets, rate limiting or snapshot pagination.
No merge, deployment, Site identity/audience change, provider-key collection, vendor
compatibility claim or real cash flow was introduced.

## 26 October 2026 — align agent discovery pagination

Inspected main, open PRs, development/roadmap, dashboard documentation and private Site
configuration. Main remains the initial backend; PR #50 checks pass. No workspace AGENTS.md
was found. Continued from #50 without merging pending work.

Hosted agent discovery ignored limit/offset and returned storage-order results. It now
matches the PostgreSQL contract: available agents with active owners, optional exact skill
filter, ID ordering, default limit 50 and maximum 100. Filtering occurs before paging and
multiple skill versions do not duplicate agents. PostgreSQL now also bounds discovery
offsets to the common safe-integer maximum. The machine manifest advertises the contract.

Validation completed:

- 10 PostgreSQL discovery/portal tests passed. Both discovery tests were rerun successfully
  after adding machine-manifest assertions.
- All 25 hosted tests passed. New cross-backend scenarios create 52 available agents and
  verify default/later/empty pages, safe offset bounds, skill filtering before paging,
  duplicate versions, paused agents, suspended owners and absence of credential fields.
  A test expectation was adjusted to the hosted skill-creation endpoint's existing 200.
- Creator/agent/superadmin browser workflows passed against both local backends.
- Hosted build, Ruff lint/format and whitespace checks passed. Existing Starlette/httpx
  warning and expected hosted readiness-test error log remain.

README, integration guide, roadmap and machine discovery updated. Hosted consumers must
now request subsequent pages instead of expecting all agents at once. Pagination is live,
not a snapshot; hosted discovery still loads records in memory and is not a scalability
claim. Discovery does not reserve capacity or certify vendor compatibility. No merge,
deployment, Site identity/audience change, centralized provider keys or real cash flows.

## 26 October 2026 — consistent direct skill visibility

Inspected main, open PRs, development/roadmap, dashboard documentation and private Site
configuration. Main remains the initial backend; PR #51 checks pass. No workspace AGENTS.md
was found. Continued on #51 without merging pending work.

Direct skill reads now require an available agent and active provider owner for outside
callers on both backends. Missing or hidden agents return 404. Credentials belonging to
the active owning account retain access to paused agents, preserving preparation workflows.
Hosted skill lists now use skill-ID ordering, matching PostgreSQL while retaining versions.
Assignments, leases, provider credentials and credit settlement are unchanged.

Validation completed:

- 11 PostgreSQL discovery/portal tests and all 26 hosted tests passed. New tests cover
  outside reads, paused owner/agent access, outside 404 for paused and suspended providers,
  reactivation without republishing, missing/unauthenticated requests and stable skill order.
- Creator/agent/superadmin browser workflows passed against both local backends. The new
  sequence publishes a skill while paused, verifies creator access and outside denial,
  activates the agent through the dashboard and verifies outside access. Existing posting,
  execution and earnings workflows continue to pass.
- Hosted build, JavaScript syntax, Ruff lint/format and whitespace checks passed. Existing
  Starlette/httpx warning and expected hosted readiness-test error log remain.

README, integration/dashboard guides and roadmap updated. Hosted consumers must handle 404
for agents they previously could inspect while paused. This controls discovery, not copies
already read or cancellation of existing work. No merge, deployment, private Site identity/
audience change, vendor compatibility claim, provider-key centralization or real cash flow.
