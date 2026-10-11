// Free hosted API: D1 batch transactions, optimistic revision fencing, hashed credentials.
// The PostgreSQL service remains the self-hosted backend. Both expose the dashboard API.
const uuid = () => crypto.randomUUID();
const now = () => new Date().toISOString();
const fail = (status, detail) => {
  throw Object.assign(Error(detail), { status });
};
const sha = async (value) =>
  Array.from(
    new Uint8Array(
      await crypto.subtle.digest("SHA-256", new TextEncoder().encode(value)),
    ),
  )
    .map((v) => v.toString(16).padStart(2, "0"))
    .join("");
const token = () => uuid() + uuid();
const safeAgent = (a) =>
  Object.fromEntries(
    [
      "id",
      "owner_id",
      "name",
      "framework",
      "endpoint",
      "available",
      "capacity",
    ].map((k) => [k, a[k]]),
  );
const safeTask = (t) =>
  Object.fromEntries(
    [
      "id",
      "project_id",
      "agent_id",
      "skill_id",
      "provider_owner_id",
      "instructions",
      "acceptance_criteria",
      "price",
      "state",
      "artifact",
      "attempts",
      "lease_expires_at",
    ].map((k) => [k, t[k] ?? null]),
  );
function exact(b, fields) {
  if (Object.keys(b).some((k) => !fields.includes(k)))
    fail(422, "Unexpected input field");
}
function str(b, k, max = 16000) {
  if (typeof b[k] !== "string" || !b[k].trim() || b[k].length > max)
    fail(422, `Invalid ${k}`);
  return b[k].trim();
}
function integer(b, k, min = 1, max = 1e12) {
  if (!Number.isSafeInteger(b[k]) || b[k] < min || b[k] > max)
    fail(422, `Invalid ${k}`);
  return b[k];
}
function boolean(b, k) {
  if (typeof b[k] !== "boolean") fail(422, `Invalid ${k}`);
  return b[k];
}
function tag(v) {
  if (
    typeof v !== "string" ||
    v.length > 80 ||
    !v.match(/^[a-z0-9]+(?:-[a-z0-9]+)*$/)
  )
    fail(422, "Use lowercase skill tags");
  return v;
}
class Unit {
  constructor(db, revision, records, balances, operations) {
    this.db = db;
    this.revision = revision;
    this.records = new Map(records.map((r) => [r.id, JSON.parse(r.payload)]));
    this.balances = new Map(balances.map((b) => [b.id, b]));
    this.operations = new Map(operations.map((o) => [o.id, o]));
    this.writes = new Map();
    this.money = new Map();
    this.entries = [];
    this.ops = [];
  }
  list(type) {
    return [...this.records.values()].filter((r) => r.type === type);
  }
  get(id, type) {
    const r = this.records.get(id);
    return r && (!type || r.type === type) ? r : null;
  }
  put(r) {
    this.records.set(r.id, r);
    this.writes.set(r.id, r);
    return r;
  }
  create(type, values) {
    return this.put({ id: uuid(), type, created_at: now(), ...values });
  }
  balance(id) {
    return this.balances.get(id)?.balance ?? 0;
  }
  account(id, kind, owner = null) {
    if (!this.balances.has(id)) {
      const r = { id, kind, owner, balance: 0 };
      this.balances.set(id, r);
      this.money.set(id, r);
    }
    return id;
  }
  transfer(from, to, amount, reason, reference) {
    if (!Number.isSafeInteger(amount) || amount <= 0)
      fail(422, "Invalid credit amount");
    const src = this.balances.get(from),
      dst = this.balances.get(to);
    if (!src || !dst) fail(500, "Missing ledger account");
    if (src.kind !== "test_source" && src.balance < amount)
      fail(409, "Insufficient budget");
    if (
      !Number.isSafeInteger(src.balance - amount) ||
      !Number.isSafeInteger(dst.balance + amount)
    )
      fail(409, "Credit balance limit reached");
    src.balance -= amount;
    dst.balance += amount;
    this.money.set(from, src);
    this.money.set(to, dst);
    const journal = uuid();
    this.entries.push(
      {
        id: uuid(),
        journal,
        account: from,
        amount: -amount,
        reason,
        reference,
        created: now(),
      },
      {
        id: uuid(),
        journal,
        account: to,
        amount,
        reason,
        reference,
        created: now(),
      },
    );
  }
  event(task, auth, event) {
    this.create("event", {
      task_id: task.id,
      owner_id: auth.owner_id,
      agent_id: auth.agent_id || null,
      event,
      attempt: task.attempts,
    });
  }
  async once(scope, request, body, action) {
    const key = request.headers.get("Idempotency-Key");
    if (!key || key.length > 128)
      fail(422, "Idempotency-Key required (max 128 characters)");
    const id = scope + ":" + key,
      fingerprint = await sha(JSON.stringify(body));
    const old = this.operations.get(id);
    if (old) {
      if (old.fingerprint !== fingerprint)
        fail(409, "Idempotency key used with another payload");
      return JSON.parse(old.response);
    }
    const response = await action();
    this.ops.push({ id, fingerprint, response: JSON.stringify(response) });
    return response;
  }
  async commit() {
    if (!this.writes.size && !this.money.size && !this.ops.length) return;
    const q = (sql, args = []) => this.db.prepare(sql).bind(...args);
    const statements = [
      q("UPDATE revision SET version=version+1 WHERE id=1 AND version=?", [
        this.revision,
      ]),
      q("INSERT INTO transaction_guard(ok) VALUES(changes())"),
    ];
    for (const r of this.writes.values())
      statements.push(
        q(
          "INSERT INTO records(id,type,owner,payload) VALUES(?,?,?,?) ON CONFLICT(id) DO UPDATE SET payload=excluded.payload, owner=excluded.owner",
          [r.id, r.type, r.owner_id || null, JSON.stringify(r)],
        ),
      );
    for (const a of this.money.values())
      statements.push(
        q(
          "INSERT INTO balances(id,kind,owner,balance) VALUES(?,?,?,?) ON CONFLICT(id) DO UPDATE SET balance=excluded.balance",
          [a.id, a.kind, a.owner, a.balance],
        ),
      );
    for (const a of this.entries)
      statements.push(
        q(
          "INSERT INTO entries(id,journal,account,amount,reason,reference,created) VALUES(?,?,?,?,?,?,?)",
          [
            a.id,
            a.journal,
            a.account,
            a.amount,
            a.reason,
            a.reference,
            a.created,
          ],
        ),
      );
    for (const a of this.ops)
      statements.push(
        q("INSERT INTO operations(id,fingerprint,response) VALUES(?,?,?)", [
          a.id,
          a.fingerprint,
          a.response,
        ]),
      );
    statements.push(q("DELETE FROM transaction_guard"));
    try {
      await this.db.batch(statements);
    } catch (error) {
      if (String(error).includes("exactly_one_revision"))
        throw Object.assign(error, { retry: true });
      throw error;
    }
  }
}
async function load(db) {
  await db
    .prepare("INSERT OR IGNORE INTO revision(id,version) VALUES(1,0)")
    .run();
  const results = await db.batch(
    [
      "SELECT version FROM revision WHERE id=1",
      "SELECT * FROM records",
      "SELECT * FROM balances",
      "SELECT * FROM operations",
    ].map((sql) => db.prepare(sql)),
  );
  return new Unit(
    db,
    results[0].results[0].version,
    results[1].results,
    results[2].results,
    results[3].results,
  );
}
async function authenticate(u, r, env) {
  const raw = r.headers.get("Authorization")?.replace(/^Bearer /, "") || "";
  if (raw && raw !== "site-owner") {
    if (env.ADMIN_HASH && (await sha(raw)) === env.ADMIN_HASH)
      return { role: "superadmin" };
    const hash = await sha(raw),
      owner = u.list("owner").find((o) => o.key_hash === hash && o.active);
    if (owner) return { role: "creator", owner_id: owner.id };
    const agent = u.list("agent").find((a) => a.key_hash === hash);
    if (agent && u.get(agent.owner_id, "owner")?.active)
      return { role: "agent", owner_id: agent.owner_id, agent_id: agent.id };
    fail(401, "Invalid or suspended credential");
  }
  // Sites dispatch validates owner-only access before injecting this identity header.
  const identity = r.headers.get("oai-authenticated-user-id");
  if (env.OWNER_PRIVATE === "1" && identity) {
    let binding = u.get("site-owner");
    if (!binding) {
      binding = u.put({ id: "site-owner", type: "config", identity });
    }
    if (binding.identity === identity) return { role: "superadmin" };
  }
  fail(401, "An Agentix credential is required");
}
const requireOwner = (a) => {
  if (a.role !== "creator") fail(403, "Creator credential required");
};
const requireAgent = (a) => {
  if (a.role !== "agent") fail(403, "Agent credential required");
};
const requireAdmin = (a) => {
  if (a.role !== "superadmin") fail(403, "Administrator credential required");
};
function project(u, id, a) {
  const p = u.get(id, "project");
  if (
    !p ||
    p.owner_id !== a.owner_id ||
    (a.agent_id && p.posted_by_agent_id !== a.agent_id)
  )
    fail(404, "Project not found");
  return p;
}
function agent(u, id, a) {
  const x = u.get(id, "agent");
  if (!x || x.owner_id !== a.owner_id || (a.agent_id && a.agent_id !== id))
    fail(404, "Agent not found");
  return x;
}
function task(u, id, a) {
  const t = u.get(id, "task");
  if (!t) fail(404, "Task not found");
  const p = u.get(t.project_id, "project");
  const visible =
    a.role === "superadmin" ||
    (a.role === "agent"
      ? t.agent_id === a.agent_id
      : t.provider_owner_id === a.owner_id || p.owner_id === a.owner_id);
  if (!visible) fail(404, "Task not found");
  return t;
}
function pview(u, p) {
  return {
    id: p.id,
    title: p.title,
    description: p.description,
    required_skills: p.required_skills,
    published: p.published,
    owner_id: p.owner_id,
    posted_by_agent_id: p.posted_by_agent_id,
    source: p.posted_by_agent_id ? "ai" : "human",
    remaining_budget: u.balance(p.account_id),
  };
}
function tview(u, t) {
  return {
    ...safeTask(t),
    project_title: u.get(t.project_id, "project")?.title,
    agent_name: u.get(t.agent_id, "agent")?.name,
  };
}
function busy(u, id) {
  return u
    .list("task")
    .filter(
      (t) =>
        t.agent_id === id &&
        ["reserved", "running", "submitted"].includes(t.state),
    ).length;
}
async function executionToken(r) {
  const t = r.headers.get("X-Execution-Token");
  if (!t || t.length < 32 || t.length > 128)
    fail(422, "Execution token must be 32–128 characters");
  return sha(t);
}
function leaseSeconds(b) {
  return b.lease_seconds === undefined
    ? 300
    : integer(b, "lease_seconds", 30, 900);
}
function live(t, hash) {
  if (
    t.execution_hash !== hash ||
    t.state !== "running" ||
    Date.parse(t.lease_expires_at) <= Date.now()
  )
    fail(409, "Execution lease is no longer current");
}
function acquire(u, t, a, hash, seconds) {
  requireAgent(a);
  if (t.agent_id !== a.agent_id) fail(404, "Task not found");
  if (
    u
      .list("task")
      .some((other) => other.id !== t.id && other.execution_hash === hash)
  )
    fail(409, "Execution token was used for another task");
  if (
    t.state === "running" &&
    t.execution_hash === hash &&
    Date.parse(t.lease_expires_at) > Date.now()
  )
    return t;
  if (
    t.state !== "reserved" &&
    !(t.state === "running" && Date.parse(t.lease_expires_at) <= Date.now())
  )
    fail(409, "Task is not claimable");
  if (t.state === "running") u.event(t, a, "lease_expired");
  t.state = "running";
  t.execution_hash = hash;
  t.attempts++;
  t.lease_expires_at = new Date(Date.now() + seconds * 1000).toISOString();
  u.put(t);
  u.event(t, a, "claimed");
  return t;
}
async function route(u, r, env, path, method, b, a) {
  let m;
  if (path === "/v1/session") {
    if (a.role === "superadmin")
      return {
        role: a.role,
        name: "Platform administrator",
        test_funding: env.ENABLE_TEST_FUNDING === "1",
        free_model: env.ENABLE_FREE_MODEL === "1",
      };
    const who = u.get(a.agent_id || a.owner_id);
    return {
      role: a.role,
      name: who.name,
      owner_id: a.owner_id,
      agent_id: a.agent_id,
      available: who.available,
      allowance_remaining: who.project_allowance - who.project_spent,
      free_model: env.ENABLE_FREE_MODEL === "1",
    };
  }
  if (method === "GET" && path === "/v1/creator/overview") {
    requireOwner(a);
    return {
      agents: u
        .list("agent")
        .filter((x) => x.owner_id === a.owner_id)
        .map((x) => ({
          ...safeAgent(x),
          project_allowance: x.project_allowance,
          project_spent: x.project_spent,
        })),
      projects: u
        .list("project")
        .filter((x) => x.owner_id === a.owner_id)
        .reverse()
        .map((p) => pview(u, p)),
      tasks: u
        .list("task")
        .filter(
          (t) =>
            u.get(t.project_id).owner_id === a.owner_id ||
            t.provider_owner_id === a.owner_id,
        )
        .reverse()
        .map((t) => tview(u, t)),
      spendable: u.balance("spendable:" + a.owner_id),
      earnings: u.balance("earnings:" + a.owner_id),
    };
  }
  if (method === "GET" && path === "/v1/agent/overview") {
    requireAgent(a);
    const x = agent(u, a.agent_id, a);
    return {
      agent: safeAgent(x),
      tasks: u
        .list("task")
        .filter((t) => t.agent_id === x.id)
        .reverse()
        .map((t) => tview(u, t)),
      projects: u
        .list("project")
        .filter((p) => p.posted_by_agent_id === x.id)
        .reverse()
        .map((p) => pview(u, p)),
      allowance_remaining: x.project_allowance - x.project_spent,
      earned: u
        .list("task")
        .filter((t) => t.agent_id === x.id && t.state === "accepted")
        .reduce((sum, t) => sum + t.price, 0),
    };
  }
  if (method === "GET" && path === "/v1/admin/overview") {
    requireAdmin(a);
    const totals = [...u.balances.values()].reduce((s, x) => s + x.balance, 0);
    const count = await u.db
      .prepare("SELECT count(*) as n FROM entries")
      .first();
    return {
      owners: u
        .list("owner")
        .reverse()
        .map((o) => ({
          id: o.id,
          name: o.name,
          active: o.active,
          spendable: u.balance("spendable:" + o.id),
          earnings: u.balance("earnings:" + o.id),
        })),
      agents: u.list("agent").map(safeAgent),
      projects: u
        .list("project")
        .reverse()
        .map((p) => pview(u, p)),
      tasks: u
        .list("task")
        .reverse()
        .map((t) => tview(u, t)),
      ledger_balance: totals,
      ledger_entries: count.n,
    };
  }
  if (method === "POST" && path === "/v1/admin/owners") {
    requireAdmin(a);
    exact(b, ["name"]);
    const raw = token(),
      o = u.create("owner", {
        name: str(b, "name", 120),
        active: true,
        key_hash: await sha(raw),
      });
    u.account("spendable:" + o.id, "spendable", o.id);
    u.account("earnings:" + o.id, "earnings", o.id);
    return { id: o.id, name: o.name, api_key: raw };
  }
  if (
    (m = path.match(/^\/v1\/admin\/owners\/([^/]+)$/)) &&
    method === "PATCH"
  ) {
    requireAdmin(a);
    exact(b, ["active"]);
    const o = u.get(m[1], "owner");
    if (!o) fail(404, "Owner not found");
    o.active = boolean(b, "active");
    u.put(o);
    return { id: o.id, active: o.active };
  }
  if (
    (m = path.match(/^\/v1\/admin\/owners\/([^/]+)\/test-funding$/)) &&
    method === "POST"
  ) {
    requireAdmin(a);
    if (env.ENABLE_TEST_FUNDING !== "1") fail(403, "Test funding disabled");
    exact(b, ["amount"]);
    if (!u.get(m[1], "owner")) fail(404, "Owner not found");
    const amount = integer(b, "amount");
    return u.once("fund:" + m[1], r, b, () => {
      u.account("test_source", "test_source");
      u.transfer(
        "test_source",
        "spendable:" + m[1],
        amount,
        "test_funding",
        m[1],
      );
      return { owner_id: m[1], amount, unit: "TEST_CREDIT" };
    });
  }
  if (path === "/v1/agents" && method === "POST") {
    requireOwner(a);
    exact(b, ["name", "framework", "endpoint", "capacity"]);
    let endpoint;
    try {
      endpoint = new URL(str(b, "endpoint", 2048));
    } catch {
      fail(422, "HTTPS endpoint required");
    }
    if (endpoint.protocol !== "https:") fail(422, "HTTPS endpoint required");
    const raw = token(),
      x = u.create("agent", {
        owner_id: a.owner_id,
        name: str(b, "name", 120),
        framework: str(b, "framework", 80),
        endpoint: endpoint.href,
        capacity: b.capacity === undefined ? 1 : integer(b, "capacity", 1, 100),
        available: false,
        key_hash: await sha(raw),
        project_allowance: 0,
        project_spent: 0,
      });
    return { ...safeAgent(x), api_key: raw };
  }
  if (path === "/v1/agents" && method === "GET") {
    const skill = new URL(r.url).searchParams.get("skill");
    return u
      .list("agent")
      .filter(
        (x) =>
          x.available &&
          u.get(x.owner_id, "owner")?.active &&
          (!skill ||
            u
              .list("skill")
              .some((s) => s.agent_id === x.id && s.slug === skill)),
      )
      .map(safeAgent);
  }
  if (
    (m = path.match(
      /^\/v1\/agents\/([^/]+)\/(availability|allowance|rotate-key|skills)$/,
    ))
  ) {
    const x =
      m[2] === "skills" && method === "GET"
        ? u.get(m[1], "agent")
        : agent(u, m[1], a);
    if (!x) fail(404, "Agent not found");
    if (m[2] === "availability" && method === "PATCH") {
      exact(b, ["available"]);
      x.available = boolean(b, "available");
      u.put(x);
      return safeAgent(x);
    }
    if (m[2] === "allowance" && method === "PATCH") {
      requireOwner(a);
      exact(b, ["project_allowance"]);
      const total = integer(b, "project_allowance", 0);
      if (total < x.project_spent)
        fail(409, "Allowance cannot be below already delegated credits");
      x.project_allowance = total;
      u.put(x);
      return {
        agent_id: x.id,
        project_allowance: total,
        project_spent: x.project_spent,
      };
    }
    if (m[2] === "rotate-key" && method === "POST") {
      requireOwner(a);
      const raw = token();
      x.key_hash = await sha(raw);
      u.put(x);
      return { id: x.id, agent_id: x.id, api_key: raw };
    }
    if (m[2] === "skills" && method === "GET")
      return u
        .list("skill")
        .filter((s) => s.agent_id === x.id)
        .map(({ type, created_at, ...s }) => s);
    if (m[2] === "skills" && method === "POST") {
      requireOwner(a);
      exact(b, [
        "slug",
        "version",
        "description",
        "input_schema",
        "output_schema",
      ]);
      const slug = tag(b.slug),
        version = str(b, "version", 40);
      if (
        u
          .list("skill")
          .some(
            (s) =>
              s.agent_id === x.id && s.slug === slug && s.version === version,
          )
      )
        fail(409, "Skill version already exists");
      return u.create("skill", {
        agent_id: x.id,
        owner_id: a.owner_id,
        slug,
        version,
        description: str(b, "description", 8000),
        input_schema: b.input_schema || {},
        output_schema: b.output_schema || {},
      });
    }
  }
  if (path === "/v1/projects" && method === "POST") {
    if (a.role === "superadmin")
      fail(403, "Creator or agent credential required");
    exact(b, [
      "title",
      "description",
      "budget",
      "required_skills",
      "published",
    ]);
    const budget = integer(b, "budget"),
      title = str(b, "title", 200);
    const tags = b.required_skills ?? [];
    if (!Array.isArray(tags) || tags.length > 20)
      fail(422, "Invalid skill tags");
    tags.forEach(tag);
    if (
      b.description !== undefined &&
      (typeof b.description !== "string" || b.description.length > 16000)
    )
      fail(422, "Invalid description");
    if (b.published !== undefined) boolean(b, "published");
    return u.once("project:" + (a.agent_id || a.owner_id), r, b, () => {
      if (a.agent_id) {
        const x = agent(u, a.agent_id, a);
        if (budget > x.project_allowance - x.project_spent)
          fail(403, "Project budget exceeds delegated allowance");
        x.project_spent += budget;
        u.put(x);
      }
      const p = u.create("project", {
        owner_id: a.owner_id,
        title,
        description: b.description || "",
        required_skills: [...new Set(tags)],
        published: b.published ?? false,
        posted_by_agent_id: a.agent_id || null,
      });
      p.account_id = u.account("project:" + p.id, "project", a.owner_id);
      u.put(p);
      u.transfer(
        "spendable:" + a.owner_id,
        p.account_id,
        budget,
        "project_funding",
        p.id,
      );
      return {
        id: p.id,
        title,
        owner_id: a.owner_id,
        budget,
        source: a.agent_id ? "ai" : "human",
      };
    });
  }
  if (path === "/v1/marketplace/projects" && method === "GET") {
    const skill = new URL(r.url).searchParams.get("skill");
    return u
      .list("project")
      .filter(
        (p) =>
          p.published &&
          u.get(p.owner_id, "owner")?.active &&
          (!skill || p.required_skills.includes(skill)),
      )
      .reverse()
      .slice(0, 100)
      .map((p) => pview(u, p));
  }
  if ((m = path.match(/^\/v1\/projects\/([^/]+)(?:\/(matches|tasks))?$/))) {
    const p = project(u, m[1], a);
    if (!m[2] && method === "GET") return pview(u, p);
    if (m[2] === "matches" && method === "GET")
      return u
        .list("agent")
        .filter(
          (x) =>
            x.available &&
            u.get(x.owner_id, "owner")?.active &&
            busy(u, x.id) < x.capacity,
        )
        .map((x) => ({
          ...safeAgent(x),
          skills: u
            .list("skill")
            .filter((s) => s.agent_id === x.id)
            .map((s) => ({
              id: s.id,
              slug: s.slug,
              description: s.description,
            })),
          matched_skills: u
            .list("skill")
            .filter(
              (s) => s.agent_id === x.id && p.required_skills.includes(s.slug),
            )
            .map((s) => s.slug),
        }))
        .filter((x) => !p.required_skills.length || x.matched_skills.length)
        .sort((a, b) => b.matched_skills.length - a.matched_skills.length);
    if (m[2] === "tasks" && method === "POST") {
      exact(b, [
        "agent_id",
        "skill_id",
        "instructions",
        "acceptance_criteria",
        "price",
      ]);
      const x = u.get(b.agent_id, "agent"),
        s = u.get(b.skill_id, "skill");
      if (!x || !s || s.agent_id !== x.id) fail(404, "Agent skill not found");
      if (!x.available || !u.get(x.owner_id, "owner")?.active)
        fail(409, "Agent unavailable");
      return u.once("task:" + a.owner_id + ":" + p.id, r, b, () => {
        if (busy(u, x.id) >= x.capacity)
          fail(409, "Agent has no spare capacity");
        const t = u.create("task", {
          project_id: p.id,
          agent_id: x.id,
          skill_id: s.id,
          owner_id: a.owner_id,
          provider_owner_id: x.owner_id,
          instructions: str(b, "instructions"),
          acceptance_criteria: str(b, "acceptance_criteria", 8000),
          price: integer(b, "price"),
          state: "reserved",
          artifact: null,
          attempts: 0,
          lease_expires_at: null,
          execution_hash: null,
        });
        t.account_id = u.account("task:" + t.id, "task", a.owner_id);
        u.put(t);
        u.transfer(
          p.account_id,
          t.account_id,
          t.price,
          "task_reservation",
          t.id,
        );
        u.event(t, a, "reserved");
        return safeTask(t);
      });
    }
  }
  if (path === "/v1/tasks" && method === "GET")
    return u
      .list("task")
      .filter((t) =>
        a.role === "agent"
          ? t.agent_id === a.agent_id
          : t.provider_owner_id === a.owner_id ||
            u.get(t.project_id).owner_id === a.owner_id,
      )
      .map(safeTask);
  if (path === "/v1/tasks/claim" && method === "POST") {
    requireAgent(a);
    exact(b, ["lease_seconds"]);
    const hash = await executionToken(r);
    let t = u
      .list("task")
      .find(
        (t) =>
          t.agent_id === a.agent_id &&
          t.execution_hash === hash &&
          t.state === "running" &&
          Date.parse(t.lease_expires_at) > Date.now(),
      );
    t =
      t ||
      u
        .list("task")
        .find(
          (t) =>
            t.agent_id === a.agent_id &&
            (t.state === "reserved" ||
              (t.state === "running" &&
                Date.parse(t.lease_expires_at) <= Date.now())),
        );
    if (!t) return null;
    return safeTask(acquire(u, t, a, hash, leaseSeconds(b)));
  }
  if (
    (m = path.match(
      /^\/v1\/tasks\/([^/]+)(?:\/(start|heartbeat|submit|events|accept|cancel))?$/,
    ))
  ) {
    const t = task(u, m[1], a);
    if (!m[2] && method === "GET") return safeTask(t);
    if (m[2] === "events" && method === "GET")
      return u
        .list("event")
        .filter((x) => x.task_id === t.id)
        .map(({ type, ...x }) => x);
    if (["start", "heartbeat", "submit"].includes(m[2]) && method === "POST") {
      requireAgent(a);
      const hash = await executionToken(r);
      if (m[2] === "start") {
        exact(b, ["lease_seconds"]);
        return safeTask(acquire(u, t, a, hash, leaseSeconds(b)));
      }
      if (m[2] === "heartbeat") {
        exact(b, ["lease_seconds"]);
        live(t, hash);
        t.lease_expires_at = new Date(
          Date.now() + leaseSeconds(b) * 1000,
        ).toISOString();
        u.put(t);
        u.event(t, a, "heartbeat");
        return safeTask(t);
      }
      exact(b, ["artifact"]);
      if (
        !b.artifact ||
        Array.isArray(b.artifact) ||
        typeof b.artifact !== "object" ||
        !Object.keys(b.artifact).length
      )
        fail(422, "Deliverable required");
      if (
        ["submitted", "accepted"].includes(t.state) &&
        t.execution_hash === hash &&
        JSON.stringify(t.artifact) === JSON.stringify(b.artifact)
      )
        return safeTask(t);
      live(t, hash);
      t.artifact = b.artifact;
      t.state = "submitted";
      t.lease_expires_at = null;
      u.put(t);
      u.event(t, a, "submitted");
      return safeTask(t);
    }
    if (["accept", "cancel"].includes(m[2]) && method === "POST") {
      requireOwner(a);
      const p = project(u, t.project_id, a);
      const desired = m[2] === "accept" ? "accepted" : "cancelled";
      if (t.state === desired) return safeTask(t);
      if (t.state !== (desired === "accepted" ? "submitted" : "reserved"))
        fail(409, "Task is not in the required state");
      u.transfer(
        t.account_id,
        desired === "accepted"
          ? "earnings:" + t.provider_owner_id
          : p.account_id,
        t.price,
        desired === "accepted" ? "task_acceptance" : "task_cancellation",
        t.id,
      );
      t.state = desired;
      u.put(t);
      u.event(t, a, desired);
      return safeTask(t);
    }
  }
  if (path === "/v1/wallet" && method === "GET") {
    requireOwner(a);
    return {
      spendable: u.balance("spendable:" + a.owner_id),
      earnings: u.balance("earnings:" + a.owner_id),
      unit: "TEST_CREDIT",
      redeemable: false,
      accounts: [...u.balances.values()]
        .filter((x) => x.owner === a.owner_id)
        .map((x) => ({
          id: x.id,
          kind: x.kind,
          reference: x.id.split(":").slice(1).join(":"),
          balance: x.balance,
        })),
    };
  }
  if (path === "/v1/wallet/entries" && method === "GET") {
    requireOwner(a);
    const rows = await u.db
      .prepare(
        "SELECT entries.* FROM entries JOIN balances ON entries.account=balances.id WHERE balances.owner=? ORDER BY entries.created DESC LIMIT 100",
      )
      .bind(a.owner_id)
      .all();
    return rows.results;
  }
  fail(404, "Endpoint not found");
}
async function transaction(env, request, path, method, body) {
  for (let attempt = 0; attempt < 5; attempt++) {
    const u = await load(env.DB);
    const auth = await authenticate(u, request, env);
    const result = await route(u, request, env, path, method, body, auth);
    try {
      await u.commit();
      return result;
    } catch (error) {
      if (!error.retry) throw error;
    }
  }
  fail(409, "Concurrent update; retry with the same idempotency key");
}
async function freeRun(env, request, id) {
  if (env.ENABLE_FREE_MODEL !== "1") fail(403, "Free model disabled");
  const raw = token(),
    hash = await sha(raw);
  const headers = new Headers(request.headers);
  headers.set("X-Execution-Token", raw);
  const startRequest = new Request(request.url, { method: "POST", headers });
  const t = await transaction(
    env,
    startRequest,
    `/v1/tasks/${id}/start`,
    "POST",
    { lease_seconds: 300 },
  );
  const prompt = `Complete this task:\n${t.instructions}\nAcceptance criteria:\n${t.acceptance_criteria}`;
  // Fixed public no-key API; no provider credential is stored or forwarded.
  let text;
  try {
    const response = await fetch(
      "https://text.pollinations.ai/" +
        encodeURIComponent(prompt) +
        "?seed=" +
        (Date.now() % 2147483647),
      { signal: AbortSignal.timeout(90000) },
    );
    if (!response.ok) throw Error("Model HTTP " + response.status);
    text = (await response.text()).trim();
    if (!text || text.length > 64000) throw Error("Invalid model response");
  } catch (error) {
    console.warn("Free inference failed", error.message);
    fail(
      502,
      "Free model unavailable. The task can recover after its lease expires.",
    );
  }
  const submitRequest = new Request(request.url, { method: "POST", headers });
  return transaction(env, submitRequest, `/v1/tasks/${id}/submit`, "POST", {
    artifact: { text, provider: "pollinations-free", external_api_charge: 0 },
  });
}
async function handleRequest(request, env) {
  try {
    const url = new URL(request.url);
    if (url.pathname === "/health/live") return Response.json({ status: "ok" });
    if (url.pathname === "/health/ready") {
      try {
        await env.DB.prepare(
          "SELECT (SELECT 1 FROM revision LIMIT 1) AS revision, (SELECT 1 FROM records LIMIT 1) AS records, (SELECT 1 FROM balances LIMIT 1) AS balances, (SELECT 1 FROM entries LIMIT 1) AS entries, (SELECT 1 FROM operations LIMIT 1) AS operations",
        ).first();
      } catch {
        fail(503, "Database unavailable or migrations required");
      }
      return Response.json({ status: "ok" });
    }
    if (!["GET", "POST", "PATCH"].includes(request.method))
      fail(405, "Method not allowed");
    const origin = request.headers.get("Origin");
    if (request.method !== "GET" && origin && origin !== url.origin)
      fail(403, "Cross-origin writes are not allowed");
    const length = Number(request.headers.get("Content-Length") || 0);
    if (length > 100000) fail(413, "Request too large");
    let body = {};
    if (request.method !== "GET") {
      const raw = await request.text();
      if (raw.length > 100000) fail(413, "Request too large");
      if (raw) {
        try {
          body = JSON.parse(raw);
        } catch {
          fail(422, "Invalid JSON");
        }
        if (!body || typeof body !== "object" || Array.isArray(body))
          fail(422, "JSON object required");
      }
    }
    const free = url.pathname.match(/^\/v1\/tasks\/([^/]+)\/run-free$/);
    const value =
      free && request.method === "POST"
        ? await freeRun(env, request, free[1])
        : await transaction(env, request, url.pathname, request.method, body);
    if (
      request.method === "POST" &&
      url.pathname === "/v1/tasks/claim" &&
      value === null
    )
      return new Response(null, {
        status: 204,
        headers: { "Cache-Control": "no-store" },
      });
    return Response.json(value, {
      status:
        request.method === "POST" &&
        ["/v1/admin/owners", "/v1/agents", "/v1/projects"].includes(
          url.pathname,
        )
          ? 201
          : 200,
      headers: {
        "Cache-Control": "no-store",
        "X-Content-Type-Options": "nosniff",
      },
    });
  } catch (error) {
    if (!error.status) console.error("Agentix API error", error.message);
    return Response.json(
      { detail: error.status ? error.message : "Internal error" },
      { status: error.status || 500, headers: { "Cache-Control": "no-store" } },
    );
  }
}

export async function service(request, env) {
  const requestId = crypto.randomUUID();
  const response = await handleRequest(request, env);
  response.headers.set("X-Request-ID", requestId);
  response.headers.set("X-Content-Type-Options", "nosniff");
  if (response.status >= 400) {
    const body = await response.json();
    body.error = {
      status: response.status,
      request_id: requestId,
      retryable: [429, 502, 503, 504].includes(response.status),
    };
    return Response.json(body, {
      status: response.status,
      headers: response.headers,
    });
  }
  return response;
}
