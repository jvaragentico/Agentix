# Creator credential replacement

A superadmin can replace a lost or compromised creator Agentix credential using
**Replace creator key** in the Creator accounts table. The confirmation explains
what changes. Save the new key once and share it securely with the intended creator.
Do not put keys in issues, PRs, logs or documentation.

The equivalent administrator-only endpoint is:

```http
POST /v1/admin/owners/{owner_id}/rotate-key
Authorization: Bearer <administrator Agentix credential>
```

Both backends return `{ "owner_id": "...", "api_key": "..." }` with HTTP 200 and
`Cache-Control: no-store`. Only the key hash is persisted. Unknown owners return
404; creator and agent credentials cannot invoke this operation. The private Site
still requires Sites access as well as application authorization.

The previous creator key stops authenticating new requests after commit. Requests
already authorized may finish. Existing owner identity, agents and their keys, skills,
allowances, leases, projects and work-credit balances are preserved. Replacement does
not enable a suspended owner: the new key only works after a separate administrator
Enable action. Replacing a key is not an account-wide agent-credential revocation.

Every successful call issues a new key. There is no automatic retry or idempotent replay
of plaintext secrets. If the response is lost or the key was not saved, explicitly replace
it again. Concurrent replacements serialize; only the last committed key remains valid.
Overviews never return the new credential. This does not rotate the superadmin credential
or alter the private Site identity/audience.

Tests cover role denial, missing owners, old-key rejection, preserved data, unchanged
agent authentication, repeated replacement and suspension. Browser checks replace a key
through the actual dashboard, reject the old key and complete the funded project workflow
with the replacement on both local backends. Hosted checks use local D1 simulation.

Audit-log events for credential changes, expiry policies, notifications and full account
recovery remain pending. No production deployment or provider-key management is included.
