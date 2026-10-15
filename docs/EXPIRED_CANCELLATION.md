# Cancelling abandoned execution

A project owner can use `POST /v1/tasks/{task_id}/cancel` with their creator credential to
cancel reserved work or a running assignment whose lease has expired. In the creator dashboard,
open the assignment after expiry and select **Cancel assignment**. Reopen or refresh an old
view to update its actions. Client time only controls visibility; the server checks the actual
lease under the task lock (PostgreSQL) or revision-checked transaction (hosted).

Active running leases, submitted deliverables and accepted work return 409. Provider owners,
agents and unrelated creators cannot cancel the buyer's assignment. Repeated cancellation
returns the cancelled task without another refund or event. Cancellation returns the entire
reservation to the project's credit account, not directly to the creator's spendable balance.
The creator can reuse the project budget or close the project once all work is terminal.
AI delegated spending is not restored. No creator earnings are generated.

If cancellation races worker recovery, only one transition succeeds. A replacement worker
that acquires a live lease first prevents cancellation; cancellation that commits first
prevents recovery. A cancelled task rejects stale start, heartbeat and submission requests,
releases assignment capacity, and retains its execution history and attempt number. The
existing `cancelled` event and `task_cancellation` journal record document the transition.

Cancellation fences Agentix state; it cannot stop an owner-managed process or undo external
tool effects. Lease expiry is not proof that the worker has stopped. Coordinate irreversible
external work independently and retain task-specific idempotency. Submitted-work disputes,
forced cancellation of active leases, automatic expiry sweeping are not implemented. [Execution attempts are capped at five](ATTEMPT_LIMITS.md);
exhausted assignments remain cancellable after expiry. No cash refund or payout exists; these remain nonredeemable work credits.

## Evidence

PostgreSQL and hosted tests cover rejection before expiry, creator authorization, duplicate
refund prevention, stale-worker fencing and cancellation racing lease recovery. PostgreSQL
tests also verify released capacity can accept replacement work. Full collaboration browser
checks remain green. A separate browser test on each local backend waits for a real 30-second
lease to expire, cancels through the creator dashboard, checks the project refund and zero
earnings, and rejects a late submission. Hosted checks use local D1 simulation, not a live
Site deployment. No schema migration is required.
