import { test } from "node:test";
import assert from "node:assert/strict";
import { DatabaseSync } from "node:sqlite";
import { readFileSync } from "node:fs";
import { service } from "../worker/service.js";
const hash = async (s) =>
  Buffer.from(
    await crypto.subtle.digest("SHA-256", new TextEncoder().encode(s)),
  ).toString("hex");
async function harness() {
  const sql = new DatabaseSync(":memory:");
  sql.exec("PRAGMA foreign_keys=ON");
  const journal = JSON.parse(
    readFileSync(new URL("../drizzle/meta/_journal.json", import.meta.url)),
  );
  for (const m of journal.entries)
    sql.exec(
      readFileSync(
        new URL("../drizzle/" + m.tag + ".sql", import.meta.url),
        "utf8",
      ),
    );
  const prepare = (text, args = []) => ({
    text,
    args,
    bind(...next) {
      return prepare(text, next);
    },
    async run() {
      return { meta: sql.prepare(text).run(...args) };
    },
    async all() {
      return { results: sql.prepare(text).all(...args) };
    },
    async first() {
      return sql.prepare(text).get(...args) || null;
    },
  });
  const DB = {
    prepare,
    batch: async (qs) => {
      sql.exec("BEGIN IMMEDIATE");
      try {
        const result = qs.map((q) =>
          /^SELECT/.test(q.text)
            ? { results: sql.prepare(q.text).all(...q.args) }
            : { meta: sql.prepare(q.text).run(...q.args) },
        );
        sql.exec("COMMIT");
        return result;
      } catch (error) {
        sql.exec("ROLLBACK");
        throw error;
      }
    },
  };
  const env = {
    DB,
    ADMIN_HASH: await hash("test-admin"),
    ENABLE_TEST_FUNDING: "1",
    ENABLE_FREE_MODEL: "1",
    OWNER_PRIVATE: "1",
  };
  async function call(
    path,
    key = "test-admin",
    method = "GET",
    body,
    extra = {},
  ) {
    const response = await service(
      new Request("https://agentix.test" + path, {
        method,
        headers: {
          ...(key ? { Authorization: "Bearer " + key } : {}),
          ...extra,
        },
        ...(body === undefined ? {} : { body: JSON.stringify(body) }),
      }),
      env,
    );
    return { status: response.status, data: await response.json() };
  }
  return { sql, call };
}
const idem = (name) => ({ "Idempotency-Key": name });
async function participants() {
  const h = await harness();
  const buyer = (
    await h.call("/v1/admin/owners", "test-admin", "POST", { name: "Buyer" })
  ).data;
  const seller = (
    await h.call("/v1/admin/owners", "test-admin", "POST", { name: "Seller" })
  ).data;
  await h.call(
    `/v1/admin/owners/${buyer.id}/test-funding`,
    "test-admin",
    "POST",
    { amount: 1000 },
    idem("fund"),
  );
  const agent = (
    await h.call("/v1/agents", seller.api_key, "POST", {
      name: "Expert",
      framework: "any-runtime",
      endpoint: "https://owner.test",
      capacity: 5,
    })
  ).data;
  await h.call(`/v1/agents/${agent.id}/availability`, agent.api_key, "PATCH", {
    available: true,
  });
  const skill = (
    await h.call(`/v1/agents/${agent.id}/skills`, seller.api_key, "POST", {
      slug: "coding",
      version: "1",
      description: "Review code",
    })
  ).data;
  return { ...h, buyer, seller, agent, skill };
}
test("concurrent duplicate funding is exactly once and concurrent overspend rolls back", async () => {
  const { call, sql } = await harness();
  const o = (
    await call("/v1/admin/owners", "test-admin", "POST", { name: "Owner" })
  ).data;
  const funding = await Promise.all(
    Array.from({ length: 8 }, () =>
      call(
        `/v1/admin/owners/${o.id}/test-funding`,
        "test-admin",
        "POST",
        { amount: 1000 },
        idem("once"),
      ),
    ),
  );
  assert.ok(funding.every((r) => r.status === 200));
  assert.equal((await call("/v1/wallet", o.api_key)).data.spendable, 1000);
  const projects = await Promise.all(
    ["a", "b"].map((x) =>
      call(
        "/v1/projects",
        o.api_key,
        "POST",
        { title: x, budget: 600 },
        idem(x),
      ),
    ),
  );
  assert.deepEqual(projects.map((r) => r.status).sort(), [201, 409]);
  assert.equal((await call("/v1/wallet", o.api_key)).data.spendable, 400);
  assert.equal(
    sql.prepare("SELECT sum(balance) as total FROM balances").get().total,
    0,
  );
});
test("task leases are exclusive and duplicate acceptance credits only the provider owner", async () => {
  const { call, buyer, seller, agent, skill, sql } = await participants();
  const p = (
    await call(
      "/v1/projects",
      buyer.api_key,
      "POST",
      { title: "Work", budget: 100 },
      idem("p"),
    )
  ).data;
  const t = (
    await call(
      `/v1/projects/${p.id}/tasks`,
      buyer.api_key,
      "POST",
      {
        agent_id: agent.id,
        skill_id: skill.id,
        instructions: "Review code",
        acceptance_criteria: "Useful notes",
        price: 50,
      },
      idem("t"),
    )
  ).data;
  const exec = "execution-token-long-enough-for-the-test";
  const headers = { "X-Execution-Token": exec };
  assert.equal(
    (await call(`/v1/tasks/${t.id}/start`, agent.api_key, "POST", {}, headers))
      .status,
    200,
  );
  assert.equal(
    (
      await call(
        `/v1/tasks/${t.id}/start`,
        agent.api_key,
        "POST",
        {},
        { "X-Execution-Token": exec + "-other" },
      )
    ).status,
    409,
  );
  assert.equal(
    (
      await call(
        `/v1/tasks/${t.id}/submit`,
        agent.api_key,
        "POST",
        { artifact: { text: "Reviewed" } },
        headers,
      )
    ).status,
    200,
  );
  const accepted = await Promise.all(
    Array.from({ length: 8 }, () =>
      call(`/v1/tasks/${t.id}/accept`, buyer.api_key, "POST"),
    ),
  );
  assert.ok(accepted.every((r) => r.status === 200));
  assert.equal((await call("/v1/wallet", seller.api_key)).data.earnings, 50);
  assert.equal((await call("/v1/wallet", buyer.api_key)).data.earnings, 0);
  assert.equal(
    sql
      .prepare(
        "SELECT count(*) as n FROM entries WHERE reason='task_acceptance'",
      )
      .get().n,
    2,
  );
  assert.equal((await call("/v1/admin/overview", agent.api_key)).status, 403);
});
test("AI posting enforces allowances, private projects and suspended owners are isolated", async () => {
  const { call, buyer, seller, agent } = await participants();
  const body = {
    title: "AI project",
    budget: 80,
    published: true,
    required_skills: ["marketing"],
  };
  assert.equal(
    (await call("/v1/projects", agent.api_key, "POST", body, idem("ai")))
      .status,
    403,
  );
  await call(
    `/v1/admin/owners/${seller.id}/test-funding`,
    "test-admin",
    "POST",
    { amount: 200 },
    idem("fund-seller"),
  );
  await call(`/v1/agents/${agent.id}/allowance`, seller.api_key, "PATCH", {
    project_allowance: 100,
  });
  const p = await call("/v1/projects", agent.api_key, "POST", body, idem("ai"));
  assert.equal(p.status, 201);
  assert.equal(p.data.source, "ai");
  assert.deepEqual(
    (await call("/v1/projects", agent.api_key, "POST", body, idem("ai"))).data,
    p.data,
  );
  assert.equal(
    (await call("/v1/agent/overview", agent.api_key)).data.allowance_remaining,
    20,
  );
  const privateProject = (
    await call(
      "/v1/projects",
      buyer.api_key,
      "POST",
      { title: "Private", budget: 50 },
      idem("private"),
    )
  ).data;
  assert.equal(
    (await call(`/v1/projects/${privateProject.id}`, agent.api_key)).status,
    404,
  );
  assert.equal(
    (await call("/v1/marketplace/projects", agent.api_key)).data.length,
    1,
  );
  await call(`/v1/admin/owners/${seller.id}`, "test-admin", "PATCH", {
    active: false,
  });
  assert.equal((await call("/v1/session", agent.api_key)).status, 401);
  assert.equal(
    (await call("/v1/marketplace/projects", buyer.api_key)).data.length,
    0,
  );
});
test("private Site owner identity binds once and credentials are never returned by overviews", async () => {
  const { call } = await harness();
  assert.equal((await call("/v1/session", "")).status, 401);
  assert.equal(
    (
      await call("/v1/session", "", "GET", undefined, {
        "oai-authenticated-user-id": "owner-identity",
      })
    ).data.role,
    "superadmin",
  );
  assert.equal(
    (
      await call("/v1/session", "", "GET", undefined, {
        "oai-authenticated-user-id": "another-identity",
      })
    ).status,
    401,
  );
  await call("/v1/admin/owners", "test-admin", "POST", {
    name: "Private owner",
  });
  const overview = await call("/v1/admin/overview");
  assert.equal(overview.status, 200);
  assert.ok(!JSON.stringify(overview.data).includes("key_hash"));
  assert.ok(!JSON.stringify(overview.data).includes("api_key"));
});
