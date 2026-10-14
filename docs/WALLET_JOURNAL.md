# Owner-scoped work-credit journal

`GET /v1/wallet/entries` requires a creator credential and returns only entries attached
to that owner's accounts. Agent credentials are rejected, including agents belonging to that
creator. Provider API keys are never used. On the private Site, native hosting authentication
is also required; it does not replace the scoped Agentix credential.

Both backends expose an array of entries with these common fields:

```json
[{"id":"entry-id","journal_id":"transfer-id","account_id":"owner-account-id","amount":50,"operation":"task_acceptance","reference":"task-id","created_at":"2026-10-14T12:00:00Z"}]
```

Positive amounts credit an account; negative amounts debit it. A journal groups the two
sides of a transfer. Transfers between an owner's own accounts produce two visible entries;
transfers involving another owner expose only this owner's side. Do not treat every positive
entry as earnings or sum absolute amounts as income. Use account kinds from `/v1/wallet` to
distinguish spendable, project, task and earnings accounts. Credits are nonredeemable work
credits, not cash, cryptocurrency or an external payment-provider balance.

`operation` describes the transfer: `test_funding`, `project_funding`, `task_reservation`,
`task_acceptance`, `task_cancellation` or `project_closure`. `reference` is the related owner,
project or task ID, depending on the operation; it does not grant access to another record.
`created_at` is the recorded timestamp with timezone (PostgreSQL journal timestamp or hosted
entry timestamp). It is not a guarantee of settlement chronology or cross-system clock order.
These additive fields preserve the existing owner scope and hosted legacy aliases.

## Creator dashboard

In the creator overview select **View credit history**. The read-only dialog shows five
entries per page with a movement label, local timestamp, account label, signed credit change
and shortened transfer reference
(the full reference is available as hover text). Use **Next page** and **Previous page** to
browse. An empty page is explicitly labeled. Loading failures show **Retry history**; no
balances change when history fails. Closing a pending view prevents its result from replacing
a later dialog. Agent and superadmin dashboards do not show this owner-history control.

The view orders entries by ID, not date, and warns that new activity can shift pages. A full
last page can show Next page leading to an empty page. Timestamps describe recorded movements; the view does not calculate income from positive
entries or promise chronological page order. Missing/invalid timestamps on older responses
show Date unavailable, and unknown operation names remain escaped text. Account labels distinguish spendable,
project budget, assignment reserve and earnings movements.

## Paging and compatibility

- `limit`: integer 1–100, default 50.
- `offset`: integer 0–9007199254740991, default 0.
- Ordering: ascending entry ID; IDs are not chronological order.
- Empty pages return `[]` with HTTP 200. Invalid pagination returns 422.

For example: `/v1/wallet/entries?limit=25&offset=25`. Use canonical decimal integers.
Advance offset by limit until a short page. Offset pages are not a snapshot across requests;
new transfers can shift results. Deduplicate by entry ID and avoid relying on this traversal
for an unattended external financial reconciliation while writes continue.

The hosted API previously ignored query parameters, returned at most 100 rows in descending
creation-time order, and used `journal`/`account` field names. It now uses bounded SQL paging
and the common contract. Legacy hosted fields, including `journal`, `account`, `reason`,
`reference` and `created`, remain present; portable clients should use the common fields.
Existing hosted callers must adapt to the new default page size and ordering.

## Verification and limits

Backend tests cover traversal, empty pages, common field aliases, invalid parameters,
owner isolation and agent denial. Browser workflows on both running local backends fetch
small pages after real project/assignment/acceptance/refund operations, reject duplicate IDs,
check account ownership and compare the entry sum with the owner's account balances.

The endpoint is read-only and does not create, settle or repair credits. No migration or
cash integration is introduced. Large-offset performance, cursor/snapshot exports, snapshot exports and external payment reconciliation remain pending. Although the
hosted journal query now applies SQL limits, its shared request loader still reads other
records into memory. Local D1 simulation is not production scalability evidence. The private
Site is unchanged until a separately authorized deployment.
