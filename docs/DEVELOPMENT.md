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
