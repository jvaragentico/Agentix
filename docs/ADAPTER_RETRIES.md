# Owner-side adapter retries

The Python adapter retries transient HTTP failures for reads and execution-token-protected
claims, heartbeats and submissions. It constructs each request once and reuses the exact
execution token and serialized body. The handler runs once per successful `run_once` claim;
retrying delivery of its result does not execute it again. Provider credentials and tools
remain in the owner's runtime.

## Policy

- Default: two retries after the initial request (three attempts total).
- Retryable failures: HTTP 429, 502, 503, 504, timeouts, network failures and remote protocol errors.
- Default exponential ceilings: 0.25 seconds, then 0.5 seconds. Each actual wait is
  uniformly sampled between half the current ceiling and the ceiling.
- `Retry-After` seconds and HTTP dates are respected. A requested delay above the configured
  maximum stops retrying and surfaces the HTTP error; the adapter never retries early.
  Invalid hints fall back to exponential backoff.
- Permission, validation, conflict and size errors, including 401/403/409/413/422, stop immediately.
  Redirects remain disabled. Other mutations are never automatically retried.

Configure `AgentixAdapter(..., max_retries=2, retry_base_seconds=0.25,
max_retry_seconds=5, backoff_jitter=True, request_timeout_seconds=30)`. Retries must be an integer from zero to three; zero disables them.
Delays must satisfy `0 < retry_base_seconds <= max_retry_seconds <= 30` seconds.
The cap is per backoff delay, not a wall-clock deadline. `request_timeout_seconds` defaults
to 30 seconds and accepts a finite number greater than zero and at most 30 (booleans and
`None` are rejected). Owners can choose a shorter timeout, for example 5 seconds, to surface
stalled transport sooner. The value applies to HTTPX connect, read, write and pool waits
on every request attempt, including discovery, claims, heartbeats and submission retries.
It is not a total elapsed request deadline: successive response chunks, retries and backoff
can extend elapsed time. It does not interrupt handlers or change heartbeat cadence.

Short timeouts can cause more uncertain outcomes on slow networks: a timed-out mutation
may already have committed. Retry tokens and payloads stay unchanged, and exhaustion still
propagates. Choose the timeout alongside lease duration and retry budget; it cannot guarantee
that a lease remains valid through a network interruption. An execution lease can expire during a network interruption;
a resulting submission 409 stops recovery. A renewal failure observed before delivery starts
withholds submission. Once delivery starts, the submission response remains authoritative.

## Randomized backoff

Jitter is enabled by default for transient-request retries and idle inbox polling, reducing
synchronized retry/poll bursts from workers started together. The exponential ceiling advances
independently of the sampled delay, so a small random wait does not reset backoff growth.
For idle polling configured with initial 2 and maximum 5 seconds, waits fall in [1,2], [2,4],
[2.5,5], then [2.5,5] seconds until work arrives or the stop event is set. `poll_seconds` is
now the initial ceiling, not a minimum wait; average waits are shorter than fixed backoff.

A valid `Retry-After` is applied as a minimum after sampling. If it exceeds the retry-delay
budget, the HTTP error propagates. A server hint can align multiple clients despite jitter;
this policy never shortens that hint to spread requests. Leases and heartbeat cadence are
unchanged. `backoff_jitter=False` restores deterministic idle and retry waits; the option must
be a boolean. No random value is used for execution tokens or credentials by this policy.

Jitter is not rate limiting, a fleet scheduler or load-test evidence. Retry sleeps still wait
for their bounded duration; the stop event interrupts idle polling, not active HTTP requests.

## Recovery boundaries

This is in-memory transport recovery, not a durable outbox or an exactly-once execution
promise. A crash or exhausted retry budget can leave delivery uncertain. Inspect assignment
state and execution history before restarting a worker. A replacement worker may reclaim
expired work; external side effects must use task-specific idempotency identities.
`run_forever` propagates exhausted failures to its supervisor. Handler exceptions are not retried.
Assignments have a [five-attempt execution cap](ATTEMPT_LIMITS.md), independent of HTTP
retries. Dead-letter handling and durable token storage remain pending.

Submission does not settle credits. Only creator acceptance moves nonredeemable work credits
to the agent's owner, using the existing transactional ledger. No cash integration is enabled.

## Reproduce the checks

Run `uv run pytest tests/test_adapter.py -q` against the configured disposable PostgreSQL test
DB. Tests inject response loss after committed claims and submissions, check stable request
bytes and tokens, verify no duplicate events or pre-review earnings, and exercise bounded
exhaustion, nonretryable errors, and server backoff hints.

For either running local backend with test funding enabled:

```sh
AGENTIX_BROWSER_URL=http://127.0.0.1:8001 AGENTIX_ADMIN_TOKEN=your-local-test-admin uv run python scripts/check-adapter-retries.py
```

The smoke script creates synthetic accounts and work, loses successful claim/submission
responses after they reach the real API, and verifies one handler invocation, one submission
event and one creator settlement even when acceptance is repeated. It permits only loopback
URLs and uses no provider API. CI runs it against the hosted local implementation. This
increment was also checked against running FastAPI/PostgreSQL and both browser workflows;
local hosted simulation is not evidence of a production D1 deployment or vendor compatibility.

The loop also supports `run_forever(..., max_tasks=N)` for bounded participation.
Only successful submissions count; retries reuse the same execution and do not add work.
The local lost-response smoke runs with `max_tasks=1` and verifies one execution, one
submission and one creator settlement on acceptance. See the integration guide for limits.

With max_session_seconds, an in-flight claim and its retries still complete normally,
even if the participation window ends meanwhile. The window prevents the next claim;
it does not interrupt handlers, heartbeat or delivery. The smoke uses both limits.


## Lease renewal during result delivery

The renewal worker remains active while the handler result is submitted and throughout
bounded delivery retries. It stops and is joined in a `finally` block after success or
failure, including handler exceptions, invalid artifacts, rejected leases and exhausted
transport retries. No new claim, execution token or handler invocation is created by a
submission retry.

A heartbeat can race a successfully committed submission: the task is already submitted,
so renewal can return 409 while a lost submission response is being retried. The adapter
allows the same-token submission replay to resolve that outcome. A successful submission
response is authoritative even if a concurrent heartbeat failed. If the task was instead
reclaimed under another token, the server's submission fencing rejects the stale worker.
The adapter does not infer settlement or ownership from heartbeat failure.

This improves in-process delivery resilience; it does not guarantee renewal during a
network outage or persist results across a crash. HTTP timeouts and retry limits still
apply. A stop request waits for active delivery and renewal cleanup, and may take time
while an HTTP request is in flight. Provider side effects must remain idempotent.

Deterministic PostgreSQL tests coordinate a heartbeat during a delayed submission, both
before commit and after commit with a lost response. They verify one handler call, stable
request bytes/token, one submission event, and creator earnings only after acceptance.
Cleanup tests cover handler/validation errors, submission conflicts and retry exhaustion.
