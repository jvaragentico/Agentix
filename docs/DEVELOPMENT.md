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
