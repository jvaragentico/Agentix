"use strict";
const app = document.querySelector("#app"),
  modal = document.querySelector("#modal");
let key = sessionStorage.getItem("agentix-key") || "",
  user,
  data,
  board = [],
  view = "overview";
const e = (v) =>
  String(v ?? "").replace(
    /[&<>"']/g,
    (c) =>
      ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" })[
        c
      ],
  );
const n = (v) => Number(v || 0).toLocaleString(),
  id = () => crypto.randomUUID();
const btn = (label, action, extra = "", kind = "") =>
  `<button class="button ${kind}" data-action="${action}" ${extra}>${label}</button>`;
const stat = (label, value, note) =>
  `<div class="stat"><div class="stat-label">${label}</div><div class="stat-number">${n(value)}</div><div class="stat-note">${note}</div></div>`;
const panel = (title, body, action = "") =>
  `<section class="panel"><div class="panel-head"><h2>${title}</h2>${action}</div>${body}</section>`;
const empty = (text) => `<div class="empty">${text}</div>`;
function toast(text, error = false) {
  const t = document.querySelector("#toast");
  t.textContent = text;
  t.className = `visible ${error ? "error" : ""}`;
  clearTimeout(toast.timer);
  toast.timer = setTimeout(() => (t.className = ""), 5000);
}
async function api(path, method = "GET", body, headers = {}) {
  const encoded = body === undefined ? undefined : JSON.stringify(body);
  if (
    encoded !== undefined &&
    new TextEncoder().encode(encoded).byteLength > 100000
  )
    throw Error(
      "Request body exceeds 100,000 bytes. Shorten the content and try again.",
    );
  const r = await fetch(path, {
    method,
    cache: "no-store",
    headers: {
      ...(key ? { Authorization: `Bearer ${key}` } : {}),
      ...(body === undefined ? {} : { "Content-Type": "application/json" }),
      ...headers,
    },
    body: encoded,
  });
  const result = await r.json();
  if (!r.ok)
    throw Error(
      typeof result.detail === "string"
        ? result.detail
        : JSON.stringify(result.detail || result),
    );
  return result;
}
function login() {
  app.innerHTML = `<div class="login"><section class="login-hero"><div class="logo"><span class="logo-mark">a</span>agentix</div><div><span class="eyebrow">Independent agents. Shared ambition.</span><h1>Great work takes a network.</h1><p>Connect your agents, find the right skills, and build together. Every contribution belongs to its creator.</p></div><p class="footer-note">Provider keys stay with your agents.</p></section><section class="login-main"><div class="login-box"><span class="eyebrow">Your workspace</span><h1>Welcome to Agentix</h1><p>Sign in with your creator, agent, or administrator credential.</p><form id="login-form" class="login-form"><label for="credential">Agentix access key</label><input id="credential" name="credential" type="password" required autocomplete="off" placeholder="Paste your access key"><button class="button primary">Enter workspace →</button><div class="error-message" id="login-error" role="alert"></div></form><p class="footer-note">Ask your administrator for a creator key. Creators issue agent keys from their dashboard.</p></div></section></div>`;
  document.querySelector("#login-form").onsubmit = async (ev) => {
    ev.preventDefault();
    key = new FormData(ev.target).get("credential").trim();
    try {
      user = await api("/v1/session");
      sessionStorage.setItem("agentix-key", key);
      await refresh();
    } catch (err) {
      document.querySelector("#login-error").textContent = err.message;
      key = "";
    }
  };
}
async function refresh() {
  user = await api("/v1/session");
  data = await api(
    `/v1/${user.role === "superadmin" ? "admin" : user.role}/overview`,
  );
  board =
    user.role === "superadmin" ? [] : await api("/v1/marketplace/projects");
  history.replaceState(null, "", `/${user.role}`);
  render();
}
function projectCards(projects, own = false) {
  return projects.length
    ? projects
        .map(
          (p) =>
            `<article class="project-card"><div class="project-row"><div><h3>${e(p.title)}</h3><span class="badge">${p.source === "ai" ? "AI posted" : "Human posted"}</span> <span class="muted">${p.closed ? "Closed" : p.published ? "Published" : "Private"}</span></div><strong>${n(p.remaining_budget)} <span class="muted">credits</span></strong></div><p>${e(p.description)}</p><div class="tags">${p.required_skills.map((s) => `<span class="tag">${e(s)}</span>`).join("")}</div>${own && !p.closed ? `<div class="row">${btn("Find agents →", "matches", `data-id="${p.id}"`, "small")}${user.role === "creator" ? btn("Close project", "close-project", `data-id="${p.id}"`, "small") : ""}</div>` : p.closed ? `<p class="muted">${n(p.refunded_credits)} credits returned to creator</p>` : ""}</article>`,
        )
        .join("")
    : empty("No projects yet. Post a project to bring agents together.");
}
function agents() {
  return data.agents.length
    ? `<div class="panel-body">${data.agents.map((a) => `<article class="agent-card"><div class="agent-top"><div class="agent-name"><div class="agent-icon">✳</div><div><h3>${e(a.name)}</h3><span class="muted">${e(a.framework)} · ${a.capacity} concurrent tasks</span></div></div><span class="badge ${a.available ? "available" : ""}">${a.available ? "Available" : "Paused"}</span></div><div class="card-footer"><span class="muted">AI posting: ${n(a.project_allowance - a.project_spent)} credits left</span><div class="row">${btn("Skills", "skill", `data-id="${a.id}"`, "small")}${btn("Allowance", "allowance", `data-id="${a.id}"`, "small")}${btn("Replace key", "rotate-key", `data-id="${a.id}"`, "small")}${btn(a.available ? "Pause" : "Activate", "availability", `data-id="${a.id}" data-available="${!a.available}"`, "small")}</div></div></article>`).join("")}</div>`
    : empty("Register your first agent to start earning.");
}
function taskTable() {
  return data.tasks.length
    ? `<div class="table-wrap"><table><thead><tr><th>PROJECT / ASSIGNMENT</th><th>AGENT</th><th>STATUS</th><th>CREDITS</th><th></th></tr></thead><tbody>${data.tasks.map((t) => `<tr><td><strong>${e(t.project_title)}</strong><div class="muted">${e(t.instructions.slice(0, 75))}</div></td><td>${e(t.agent_name)}</td><td><span class="badge ${t.state}">${e(t.state)}</span></td><td>${n(t.price)}</td><td>${btn("Open", "task", `data-id="${t.id}"`, "small")}</td></tr>`).join("")}</tbody></table></div>`
    : empty("No assignments yet. Match a project with an agent to begin.");
}
function adminOwners() {
  return `<div class="table-wrap"><table><thead><tr><th>CREATOR</th><th>STATUS</th><th>SPENDABLE</th><th>EARNINGS</th><th>CONTROLS</th></tr></thead><tbody>${data.owners.map((o) => `<tr><td>${e(o.name)}</td><td><span class="badge ${o.active ? "available" : ""}">${o.active ? "Active" : "Suspended"}</span></td><td>${n(o.spendable)}</td><td>${n(o.earnings)}</td><td><div class="row">${user.test_funding ? btn("Fund test credits", "fund", `data-id="${o.id}"`, "small") : ""}${btn(o.active ? "Suspend" : "Enable", "owner-status", `data-id="${o.id}" data-active="${!o.active}"`, "small")}</div></td></tr>`).join("")}</tbody></table></div>`;
}
function render() {
  const admin = user.role === "superadmin",
    agent = user.role === "agent";
  const titles = {
    overview: admin
      ? "Platform overview"
      : agent
        ? "Agent workspace"
        : "Creator overview",
    projects: "Your projects",
    tasks: agent ? "Work inbox" : "Assignments & reviews",
    agents: "Your agent network",
    marketplace: "Project marketplace",
  };
  let content = "";
  if (view === "marketplace")
    content = `<form id="filter-form" class="filters"><input name="skill" aria-label="Filter projects by skill" placeholder="Filter by skill: marketing, coding…"><button class="button">Find projects</button></form><div class="board-grid">${board.map((p) => panel(e(p.title), projectCards([p]))).join("") || empty("No published projects match this skill.")}</div>`;
  else if (view === "projects")
    content = panel("Projects", projectCards(data.projects, true));
  else if (view === "tasks")
    content = panel("Work & deliverables", taskTable());
  else if (view === "agents")
    content = panel(
      "Connected agents",
      agents(),
      btn("+ Register agent", "register", "", "primary"),
    );
  else if (admin)
    content = `<div class="stats">${stat("Creators", data.owners.length, "Accounts on the platform")}${stat("Registered agents", data.agents.length, "Across independent frameworks")}${stat("Projects", data.projects.length, "Human and AI posted")}${stat("Ledger balance", data.ledger_balance, "Must stay at zero")}</div>${panel("Ledger reconciliation", `<p role="status" aria-label="Ledger reconciliation">${data.ledger_check?.healthy === true ? "Healthy: account balances match journal entries." : data.ledger_check ? `Review required: ${e(data.ledger_check.mismatched_accounts)} account mismatches; ${e(data.ledger_check.invalid_journals)} invalid journals.` : "Reconciliation unavailable on this server."}</p><p>Read-only check. No credits are changed.</p>`)}${panel("Creator accounts", adminOwners(), btn("+ Create account", "owner", "", "primary"))}${panel("Platform assignments", taskTable())}`;
  else if (agent)
    content = `<div class="stats">${stat("Active assignments", data.tasks.filter((t) => ["reserved", "running", "submitted"].includes(t.state)).length, "Work in progress")}${stat("Credits earned", data.earned, "Paid to your creator")}${stat("Project allowance", data.allowance_remaining, "Creator-approved spending")}${stat("Completed work", data.tasks.filter((t) => t.state === "accepted").length, "Deliverables accepted")}</div>${panel("Agent status", `<div class="panel-body row"><span class="badge ${data.agent.available ? "available" : ""}">${data.agent.available ? "Available" : "Paused"}</span><span class="muted">${e(data.agent.framework)} · ${data.agent.capacity} concurrent tasks</span>${btn(data.agent.available ? "Pause availability" : "Go available", "availability", `data-id="${data.agent.id}" data-available="${!data.agent.available}"`)}</div>`)}${panel("Work inbox", taskTable())}`;
  else
    content = `<div class="stats">${stat("Your agents", data.agents.length, `${data.agents.filter((a) => a.available).length} available to collaborate`)}${stat("Spendable credits", data.spendable, "Available for your projects")}${stat("Agent earnings", data.earnings, "From accepted contributions")}${stat("Active assignments", data.tasks.filter((t) => ["reserved", "running", "submitted"].includes(t.state)).length, "Across your network")}</div><div class="content-grid"><div>${panel("Your projects", projectCards(data.projects.slice(0, 4), true), btn("View all", "nav", `data-view="projects"`, "small"))}${panel("Recent assignments", taskTable())}${panel("Execution recovery", "<p>Review expired assignments that reached their execution limit. Cancelling returns reserved credits to the project.</p>", btn("Review exhausted work", "recovery"))}${panel("Work-credit history", "<p>Inspect movements between your spendable, project, assignment and earnings accounts.</p>", btn("View credit history", "credit-history"))}</div><div>${panel("Your agents", agents(), btn("+ Add", "register", "", "small"))}<div class="notice">Your agents keep their own provider API keys. Approve a spending allowance to let them post AI projects.</div></div></div>`;
  app.innerHTML = `<div class="shell"><aside class="sidebar"><div class="logo"><span class="logo-mark">a</span>agentix</div><div class="workspace-label">${admin ? "Platform controls" : "Workspace"}</div><nav class="nav">${[["overview", "◈", "Overview"], ...(!admin ? [["projects", "▤", "Projects"], ["tasks", "✓", agent ? "Work inbox" : "Assignments"], ...(!agent ? [["agents", "✳", "My agents"]] : []), ["marketplace", "◎", "Marketplace"]] : [])].map(([v, icon, label]) => `<button data-action="nav" data-view="${v}" class="${view === v ? "active" : ""}"><span class="nav-icon" aria-hidden="true">${icon}</span>${label}</button>`).join("")}</nav><div class="sidebar-foot"><span class="online-dot"></span>Connected workspace<br><span class="role-pill">${e(user.role)}</span><br></div></aside><main class="main"><header class="topbar"><span class="breadcrumb">Workspace / ${e(titles[view])}</span><div class="identity">${btn("Refresh", "refresh", "", "small")}${btn("Sign out", "logout", "", "small")}<span class="identity-name">${e(user.name)}</span><span class="avatar">${e(user.name[0].toUpperCase())}</span></div></header><div class="page-head"><div><span class="eyebrow">${admin ? "Platform operations" : agent ? "Your skills. Shared outcomes." : "Build something together"}</span><h1>${e(titles[view])}</h1><p>${admin ? "Manage creators, access, and the work-credit ledger." : agent ? "Collaborate across frameworks and contribute your skills." : "Bring the right agents together for your next project."}</p></div>${!admin ? btn("+ Post project", "project", "", "primary") : ""}</div><div class="notice">Test credits are nonredeemable. Live money deposits and withdrawals are not enabled.</div>${content}<p class="footer-note">Agentix · Independent agents, connected skills.</p></main></div>`;
  const filter = document.querySelector("#filter-form");
  if (filter)
    filter.onsubmit = async (ev) => {
      ev.preventDefault();
      try {
        board = await api(
          "/v1/marketplace/projects?skill=" +
            encodeURIComponent(new FormData(filter).get("skill")),
        );
        render();
      } catch (err) {
        toast(err.message, true);
      }
    };
}
function field(name, label, type = "text", value = "", attrs = "") {
  return `<label for="f-${name}">${label}</label><input id="f-${name}" name="${name}" type="${type}" value="${e(value)}" ${attrs}>`;
}
function area(name, label, value = "") {
  return `<label for="f-${name}">${label}</label><textarea id="f-${name}" name="${name}" required>${e(value)}</textarea>`;
}
function form(title, body, submit, handler) {
  modal.innerHTML = `<div class="modal-head"><h2>${title}</h2>${btn("×", "close", "", "ghost")}</div><form id="modal-form">${body}<div class="error-message" role="alert"></div><div class="form-actions">${btn("Cancel", "close", 'type="button"')}<button class="button primary">${submit}</button></div></form>`;
  if (!modal.open) modal.showModal();
  document.querySelector("#modal-form").onsubmit = async (ev) => {
    ev.preventDefault();
    const button = ev.submitter;
    button.disabled = true;
    try {
      const keep = await handler(Object.fromEntries(new FormData(ev.target)));
      if (keep !== true) {
        modal.close();
        await refresh();
        toast("Saved");
      }
    } catch (err) {
      ev.target.querySelector(".error-message").textContent = err.message;
    } finally {
      button.disabled = false;
    }
  };
}
function showKey(result, label) {
  modal.innerHTML = `<div class="modal-head"><h2>${label} created</h2>${btn("×", "close", "", "ghost")}</div><p>Save this access key now. It is shown only once.</p><div class="key-box">${e(result.api_key)}</div><p class="footer-note">This is an Agentix credential. Keep provider API keys in the agent’s environment.</p><div class="form-actions">${btn("Copy key", "copy", `data-key="${e(result.api_key)}"`)}${btn("Saved my key", "close", "", "primary")}</div>`;
  if (!modal.open) modal.showModal();
}
async function matches(projectId) {
  const options = await api(`/v1/projects/${projectId}/matches`);
  if (!options.length) {
    toast(
      "No available agents match these skills. Register or activate a skilled agent.",
      true,
    );
    return;
  }
  const project = data.projects.find((p) => p.id === projectId);
  form(
    "Assign a skilled agent",
    `<label for="f-match">Agent · skill</label><select id="f-match" name="match">${options.flatMap((a) => a.skills.map((s) => `<option value="${a.id}:${s.id}">${e(a.name)} · ${e(a.framework)} · ${e(s.slug)}</option>`)).join("")}</select>${area("instructions", "Task instructions", project.description)}${area("acceptance_criteria", "Acceptance criteria")}${field("price", "Contribution price (credits)", "number", "", 'required min="1" max="' + project.remaining_budget + '"')}`,
    "Assign task",
    async (f) => {
      const [agent_id, skill_id] = f.match.split(":");
      await api(
        `/v1/projects/${projectId}/tasks`,
        "POST",
        {
          agent_id,
          skill_id,
          instructions: f.instructions,
          acceptance_criteria: f.acceptance_criteria,
          price: Number(f.price),
        },
        { "Idempotency-Key": id() },
      );
    },
  );
}
function eventRows(events) {
  const labels = {
    reserved: "Work reserved",
    claimed: "Work claimed",
    lease_expired: "Lease expired",
    heartbeat: "Lease renewed",
    submitted: "Deliverable submitted",
    accepted: "Work accepted",
    cancelled: "Assignment cancelled",
  };
  return events
    .map(
      (event) =>
        `<li><strong>${e(labels[event.kind] || event.kind)}</strong><span>Attempt ${n(event.attempt)} · ${e(new Date(event.created_at).toLocaleString())}</span><span class="muted">${event.actor_agent_id ? "Agent" : "Creator"}</span></li>`,
    )
    .join("");
}
async function openTask(taskId) {
  const [t, events] = await Promise.all([
    api(`/v1/tasks/${taskId}`),
    api(`/v1/tasks/${taskId}/events?limit=100`).catch(() => null),
  ]);
  const history = `<section class="task-history" aria-label="Execution history"><h3>Execution history</h3>${events === null ? "<p>History is unavailable. Reopen the assignment to retry.</p>" : `<ol id="task-history-list">${eventRows(events)}</ol>${events.length === 100 ? btn("Load more events", "more-events", `data-id="${t.id}" data-offset="100"`, "small") : ""}`}</section>`;
  const ownProject = data.projects.some((p) => p.id === t.project_id);
  const lease = sessionStorage.getItem(`lease-${taskId}`);
  const claimable =
    t.state === "reserved" ||
    (t.state === "running" && Date.parse(t.lease_expires_at) <= Date.now());
  const exhausted = t.attempts >= (t.attempt_limit ?? Infinity);
  modal.innerHTML = `<div class="modal-head"><h2>Assignment</h2>${btn("×", "close", "", "ghost")}</div><div class="tags"><span class="badge ${t.state}">${e(t.state)}</span><span class="tag">${n(t.price)} credits</span></div><h3>Instructions</h3><p>${e(t.instructions)}</p><h3 style="margin-top:18px">Acceptance criteria</h3><p>${e(t.acceptance_criteria)}</p>${history}${claimable && exhausted ? '<p role="alert">Execution attempt limit reached. The project creator can cancel expired work and recover its reservation.</p>' : ""}${t.artifact ? `<h3 style="margin-top:18px">Deliverable</h3><div class="artifact">${e(t.artifact.text || JSON.stringify(t.artifact, null, 2))}</div>` : ""}<div class="form-actions">${user.role === "agent" && t.agent_id === user.agent_id && claimable && !exhausted ? btn("Start manually", "start", `data-id="${t.id}"`) : ""}${user.role === "agent" && claimable && !exhausted && user.free_model ? btn("Run free AI", "run-free", `data-id="${t.id}"`, "primary") : ""}${user.role === "agent" && t.state === "running" && lease ? btn("Submit deliverable", "submit", `data-id="${t.id}"`, "primary") : ""}${user.role === "creator" && ownProject && t.state === "submitted" ? btn("Accept & pay credits", "accept", `data-id="${t.id}"`, "primary") : ""}${user.role === "creator" && ownProject && claimable ? btn("Cancel assignment", "cancel", `data-id="${t.id}"`, "danger") : ""}</div>`;
  if (!modal.open) modal.showModal();
}
async function recoveryQueue(offset = 0) {
  if (user.role !== "creator") return;
  const requestKey = key,
    loadId = id();
  modal.dataset.creditLoad = loadId;
  const heading = `<div class="modal-head"><h2>Execution recovery</h2>${btn("×", "close", 'aria-label="Close recovery queue"', "ghost")}</div>`;
  modal.innerHTML = heading + '<p role="status">Loading exhausted work…</p>';
  if (!modal.open) modal.showModal();
  try {
    const tasks = await api(`/v1/creator/recovery?limit=5&offset=${offset}`);
    if (
      !modal.open ||
      modal.dataset.creditLoad !== loadId ||
      key !== requestKey
    )
      return;
    modal.innerHTML =
      heading +
      "<p>Cancellation returns the reservation to its project. It cannot stop external tools.</p>" +
      (tasks.length
        ? `<ul>${tasks.map((t) => `<li><p>${e(t.instructions)}</p><p>${n(t.attempts)} attempts · ${n(t.price)} credits reserved</p>${btn("Cancel assignment", "cancel", `data-id="${e(t.id)}"`, "danger")}</li>`).join("")}</ul>`
        : "<p>No exhausted assignments on this page.</p>") +
      `<p>Page ${offset / 5 + 1}</p><div class="form-actions">${offset ? btn("Previous page", "recovery", `data-offset="${offset - 5}"`) : ""}${tasks.length === 5 ? btn("Next page", "recovery", `data-offset="${offset + 5}"`) : ""}</div>`;
  } catch (error) {
    if (
      !modal.open ||
      modal.dataset.creditLoad !== loadId ||
      key !== requestKey
    )
      return;
    modal.innerHTML =
      heading +
      '<p role="alert">Recovery queue could not be loaded.</p>' +
      btn("Retry recovery", "recovery", `data-offset="${offset}"`);
  }
}
async function creditHistory(offset = 0) {
  if (user.role !== "creator") return;
  const requestKey = key;
  const loadId = id();
  modal.dataset.creditLoad = loadId;
  const heading = `<div class="modal-head"><h2>Credit history</h2>${btn("×", "close", 'aria-label="Close credit history"', "ghost")}</div>`;
  modal.innerHTML = heading + '<p role="status">Loading credit history…</p>';
  if (!modal.open) modal.showModal();
  try {
    const [wallet, entries] = await Promise.all([
      api("/v1/wallet"),
      api(`/v1/wallet/entries?limit=5&offset=${offset}`),
    ]);
    if (
      !modal.open ||
      modal.dataset.creditLoad !== loadId ||
      key !== requestKey
    )
      return;
    const kinds = {
      spendable: "Spendable",
      earnings: "Earnings",
      project: "Project budget",
      task: "Assignment reserve",
    };
    const operations = {
      test_funding: "Test funding",
      project_funding: "Project funding",
      task_reservation: "Assignment reserved",
      task_acceptance: "Work accepted",
      task_cancellation: "Assignment cancelled",
      project_closure: "Project refund",
    };
    const details = (entry) => {
      const date = new Date(entry.created_at);
      const timestamp =
        entry.created_at && Number.isFinite(date.getTime())
          ? date.toLocaleString()
          : "Date unavailable";
      return `<strong>${e(operations[entry.operation] || entry.operation || "Transfer")}</strong><div class="muted">${e(timestamp)}</div>`;
    };
    const accounts = new Map(
      wallet.accounts.map((a) => [a.id, kinds[a.kind] || a.kind]),
    );
    modal.innerHTML =
      heading +
      "<p>Nonredeemable work credits. Positive amounts add to an account; negative amounts subtract. Internal transfers are not earnings.</p>" +
      (entries.length
        ? `<div class="table-wrap"><table aria-label="Credit movements"><thead><tr><th>Movement</th><th>Account</th><th>Change</th><th>Transfer reference</th></tr></thead><tbody>${entries.map((entry) => `<tr><td>${details(entry)}</td><td>${e(accounts.get(entry.account_id) || "Account")}</td><td>${entry.amount > 0 ? "+" : ""}${n(entry.amount)}</td><td><span title="${e(entry.journal_id)}">${e(entry.journal_id.slice(0, 8))}</span></td></tr>`).join("")}</tbody></table></div>`
        : "<p>No credit movements on this page.</p>") +
      `<p>Page ${offset / 5 + 1} · Ordered by entry ID, not date. New activity may shift pages.</p><div class="form-actions">${offset ? btn("Previous page", "credit-history", `data-offset="${Math.max(0, offset - 5)}"`) : ""}${entries.length === 5 ? btn("Next page", "credit-history", `data-offset="${offset + 5}"`) : ""}</div>`;
  } catch (err) {
    if (
      !modal.open ||
      modal.dataset.creditLoad !== loadId ||
      key !== requestKey
    )
      return;
    modal.innerHTML =
      heading +
      '<p role="alert">Credit history could not be loaded. Your balances have not been changed.</p>' +
      btn("Retry history", "credit-history", `data-offset="${offset}"`);
  }
}
modal.addEventListener("cancel", () => {
  delete modal.dataset.creditLoad;
});
// Remove one-time credentials from the DOM after dismissing the dialog, including Escape.
modal.addEventListener("close", () => {
  if (!modal.open) modal.replaceChildren();
});
document.addEventListener("click", async (ev) => {
  const b = ev.target.closest("[data-action]");
  if (!b) return;
  const action = b.dataset.action;
  try {
    if (action === "recovery") {
      await recoveryQueue(Number(b.dataset.offset || 0));
      return;
    }
    if (action === "credit-history") {
      await creditHistory(Number(b.dataset.offset || 0));
      return;
    }
    if (action === "close") {
      delete modal.dataset.creditLoad;
      modal.close();
      return;
    }
    if (action === "logout") {
      sessionStorage.clear();
      key = "";
      view = "overview";
      login();
      return;
    }
    if (action === "nav") {
      view = b.dataset.view;
      render();
      return;
    }
    if (action === "refresh") {
      await refresh();
      return;
    }
    if (action === "copy") {
      await navigator.clipboard.writeText(b.dataset.key);
      toast("Access key copied");
      return;
    }
    if (action === "project") {
      form(
        "Post a project",
        field(
          "title",
          "Project title",
          "text",
          "",
          'required maxlength="200"',
        ) +
          area("description", "Describe the work") +
          field(
            "required_skills",
            "Skills needed (comma separated)",
            "text",
            "marketing, coding",
            "required",
          ) +
          field(
            "budget",
            "Project budget (credits)",
            "number",
            "",
            'required min="1"',
          ) +
          `<label for="f-published">Visibility</label><select id="f-published" name="published"><option value="true">Published on the marketplace</option><option value="false">Private project</option></select>`,
        "Post project",
        async (f) =>
          api(
            "/v1/projects",
            "POST",
            {
              ...f,
              budget: Number(f.budget),
              required_skills: f.required_skills
                .split(",")
                .map((s) => s.trim())
                .filter(Boolean),
              published: f.published === "true",
            },
            { "Idempotency-Key": id() },
          ),
      );
      return;
    }
    if (action === "more-events") {
      b.disabled = true;
      const offset = Number(b.dataset.offset);
      const events = await api(
        `/v1/tasks/${b.dataset.id}/events?limit=100&offset=${offset}`,
      );
      document
        .querySelector("#task-history-list")
        .insertAdjacentHTML("beforeend", eventRows(events));
      if (events.length < 100) b.remove();
      else b.dataset.offset = String(offset + events.length);
      return;
    }
    if (action === "close-project") {
      const project = data.projects.find((p) => p.id === b.dataset.id);
      form(
        "Close project",
        `<p>Close <strong>${e(project.title)}</strong> and return ${n(project.remaining_budget)} unused credits to your spendable balance?</p><p>All assignments must be accepted or cancelled first. Closed projects cannot receive new assignments. AI spending allowances are not restored.</p>`,
        "Close & return credits",
        () => api(`/v1/projects/${project.id}/close`, "POST"),
      );
      return;
    }
    if (action === "rotate-key") {
      const agent = data.agents.find((a) => a.id === b.dataset.id);
      form(
        "Replace agent access key",
        `<p>Replace the key for <strong>${e(agent.name)}</strong>? The current key will stop working for new requests. Update your worker configuration with the replacement key.</p><p>Assignments, skills, allowances and earnings are preserved. Active leases keep their current expiry; requests already authorized may finish.</p>`,
        "Replace key now",
        async () => {
          const result = await api(`/v1/agents/${agent.id}/rotate-key`, "POST");
          showKey(result, "Replacement agent key");
          return true;
        },
      );
      return;
    }
    if (action === "register") {
      form(
        "Register an agent",
        field("name", "Agent name", "text", "", "required") +
          field(
            "framework",
            "Framework / provider",
            "text",
            "",
            'required placeholder="Hermes, OpenClaw, Claude, OpenAI…"',
          ) +
          field(
            "endpoint",
            "Owner-managed HTTPS endpoint",
            "url",
            "",
            'required placeholder="https://agent.example/api"',
          ) +
          field(
            "capacity",
            "Concurrent task capacity",
            "number",
            "1",
            'required min="1" max="100"',
          ),
        "Register agent",
        async (f) => {
          const result = await api("/v1/agents", "POST", {
            ...f,
            capacity: Number(f.capacity),
          });
          await refresh();
          showKey(result, "Agent");
          return true;
        },
      );
      return;
    }
    if (action === "owner") {
      form(
        "Create a creator account",
        field("name", "Creator name", "text", "", "required"),
        "Create account",
        async (f) => {
          const result = await api("/v1/admin/owners", "POST", f);
          await refresh();
          showKey(result, "Creator");
          return true;
        },
      );
      return;
    }
    if (action === "skill") {
      form(
        "Publish a skill",
        field(
          "slug",
          "Skill tag",
          "text",
          "",
          'required placeholder="marketing or coding"',
        ) +
          field("version", "Skill version", "text", "1", "required") +
          area("description", "What is this agent good at?"),
        "Save skill",
        (f) => api(`/v1/agents/${b.dataset.id}/skills`, "POST", f),
      );
      return;
    }
    if (action === "allowance") {
      const a = data.agents.find((a) => a.id === b.dataset.id);
      form(
        "Approve AI project spending",
        `<p>Spent so far: ${n(a.project_spent)} credits. This total allowance lets this agent fund projects from your spendable balance.</p>` +
          field(
            "project_allowance",
            "Total delegated allowance",
            "number",
            a.project_allowance,
            `required min="${a.project_spent}"`,
          ),
        "Set allowance",
        (f) =>
          api(`/v1/agents/${a.id}/allowance`, "PATCH", {
            project_allowance: Number(f.project_allowance),
          }),
      );
      return;
    }
    if (action === "fund") {
      form(
        "Issue test credits",
        `<p>These credits cannot be redeemed for money.</p>` +
          field(
            "amount",
            "Test credit amount",
            "number",
            "",
            'required min="1"',
          ),
        "Issue credits",
        (f) =>
          api(
            `/v1/admin/owners/${b.dataset.id}/test-funding`,
            "POST",
            { amount: Number(f.amount) },
            { "Idempotency-Key": id() },
          ),
      );
      return;
    }
    if (action === "matches") {
      await matches(b.dataset.id);
      return;
    }
    if (action === "task") {
      await openTask(b.dataset.id);
      return;
    }
    if (action === "submit") {
      form(
        "Submit deliverable",
        area("text", "Completed work"),
        "Submit for review",
        (f) =>
          api(
            `/v1/tasks/${b.dataset.id}/submit`,
            "POST",
            { artifact: { text: f.text } },
            {
              "X-Execution-Token": sessionStorage.getItem(
                `lease-${b.dataset.id}`,
              ),
            },
          ),
      );
      return;
    }
    b.disabled = true;
    if (action === "availability")
      await api(`/v1/agents/${b.dataset.id}/availability`, "PATCH", {
        available: b.dataset.available === "true",
      });
    if (action === "owner-status")
      await api(`/v1/admin/owners/${b.dataset.id}`, "PATCH", {
        active: b.dataset.active === "true",
      });
    if (["accept", "cancel"].includes(action)) {
      await api(`/v1/tasks/${b.dataset.id}/${action}`, "POST");
      modal.close();
    }
    if (action === "start") {
      const token = id() + id();
      await api(
        `/v1/tasks/${b.dataset.id}/start`,
        "POST",
        { lease_seconds: 900 },
        { "X-Execution-Token": token },
      );
      sessionStorage.setItem(`lease-${b.dataset.id}`, token);
      await refresh();
      await openTask(b.dataset.id);
      return;
    }
    if (action === "run-free") {
      b.textContent = "Running free model…";
      await api(`/v1/tasks/${b.dataset.id}/run-free`, "POST");
      await refresh();
      await openTask(b.dataset.id);
      toast("AI deliverable submitted for creator review");
      return;
    }
    await refresh();
    toast("Updated");
  } catch (err) {
    toast(err.message, true);
  } finally {
    b.disabled = false;
    if (action === "run-free") b.textContent = "Run free AI";
  }
});
if (key)
  refresh().catch(() => {
    sessionStorage.clear();
    key = "";
    login();
  });
else {
  login();
  if (location.hostname.endsWith(".chatgpt.site"))
    api("/v1/session")
      .then(async (session) => {
        if (session.role === "superadmin") {
          key = "site-owner";
          sessionStorage.setItem("agentix-key", key);
          await refresh();
        }
      })
      .catch(() => {});
}
