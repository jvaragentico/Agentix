# Creator recovery queue

Select **Review exhausted work** in the creator overview to find running assignments whose
leases have expired after reaching the five-attempt limit. The dialog shows instructions,
attempt count and reserved credits, with five-entry pages and a cancellation action. It has
explicit empty, loading and retry states. Closing a pending read prevents its result from
replacing a later dialog. This queue is independent of the overview's recent assignment list.

`GET /v1/creator/recovery` exposes the same owner-scoped queue to creator clients on both
backends. Agent credentials are rejected. Being the provider owner alone does not grant access
to the buyer's recovery queue. Responses use the common task representation with no execution
secrets. Only running tasks at/above the limit with expired or absent leases are included;
reserved, live-running, submitted, accepted and cancelled tasks are excluded.

Parameters: `limit` defaults to 25 and accepts integers 1–100; `offset` defaults to zero and
accepts integers through 9007199254740991. Entries are sorted by task ID. Filtering occurs
before pagination; an empty page returns HTTP 200 with `[]`. Invalid pagination returns 422.
The backend takes one time reading for the query/filter. Results are not a snapshot across
pages. New activity and cancellation can move entries between pages; reopen from page one
when reviewing changes.

## Recovery action

Cancellation reuses `POST /v1/tasks/{task_id}/cancel`. It returns credits to the project,
releases capacity and fences later submissions exactly once. The server rechecks authorization
and state: stale UI data never grants permission to cancel protected work. After cancellation,
the dialog closes and the overview refreshes; reopen the queue for current results. No bulk
cancellation, automatic refund or hidden execution restart is introduced.

Review context before cancelling. This action cannot stop tools running in an owner-managed
environment or undo their effects. See [expired cancellation](EXPIRED_CANCELLATION.md).
The queue is read-only until the creator explicitly selects Cancel assignment. No cash payout
or provider-key handling is involved.

## Evidence and limits

Backend tests perform real claims up to five attempts with controlled lease expiry, verify
queue visibility only after expiry, enforce owner/agent isolation and pagination, and confirm
removal after cancellation. Browser checks cover a real empty queue and a simulated read
failure/retry. The populated-queue browser response is injected to represent five attempts;
its cancellation still hits a real assignment after a real 30-second lease expires and
verifies the actual project refund and stale-submission rejection. These checks run locally
on FastAPI/PostgreSQL and hosted Worker/D1 simulation, not the live Site.

Hosted requests still load records in memory. Indexed hosted queries, detailed project labels,
notifications, bulk workflows, snapshot pagination and large-scale operations testing remain
pending. No schema migration or deployment is required to review this branch.
