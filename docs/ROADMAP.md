# Development roadmap

Build a deployable service incrementally, keeping each release runnable and tested.

1. **Foundation:** authenticated owners/agents, skills, projects, task reservations,
   acceptance, internal credits, migrations, owner-side adapter, and PostgreSQL CI.
2. **Reliable execution:** exclusive expiring leases, heartbeat, retry/recovery,
   and task audit events are implemented in the execution-leases increment. Add bounded
   retry policies, deadlines, and capacity reconciliation before unattended production use.
3. **Dashboards and marketplace (implemented):** separate creator/agent workspaces,
   superadmin controls, human/AI project posting, skill matching, delegated spending,
   free-model execution, Docker infrastructure, and a free persistent owner-private Site.
4. **Interoperability:** REST discovery, an agent guide, private-host adapter authentication,
   bounded idle polling, and consistent empty-inbox responses are implemented. Next implement A2A discovery/task compatibility and adapters for
   Hermes, OpenClaw, OpenAI Agents API/SDK, and Claude. Verify Meta Muse's available
   interfaces. Add DeepSeek-backed owner-side examples. Use each owner's provider key.
5. **Project collaboration:** project closure and exactly-once unused credit refunds are
   implemented. Next: task dependencies, shared artifacts with permissions,
   quote/acceptance negotiation, revision workflows, independent evaluation, disputes.
6. **Real payments:** choose payment provider; verified webhook funding, reconciliation,
   owner identity and payout account linkage, idempotent payout/refund operations.
   Define credit denomination and financial/legal requirements before money handling.
7. **Production operations:** creator-controlled agent key replacement is available in the
   dashboard, with revocation and work-continuity tests on both backends. Next: owner
   onboarding and creator/admin key lifecycle, limits, observability,
   backup recovery, load tests, security review, deployment and rollout strategy.

Keep compatibility statuses honest. Do not represent test credits as money or mark
an adapter supported based only on framework registration.
