import { test as base, expect } from "@playwright/test";
import { readFileSync } from "node:fs";
const test = base.extend({
  request: async ({ request }, use) => {
    await use(
      Object.fromEntries(
        ["get", "post", "patch"].map((method) => [
          method,
          (url, options = {}) =>
            request[method](url, { ...options, maxRedirects: 0 }),
        ]),
      ),
    );
  },
});
const admin =
  process.env.AGENTIX_ADMIN_TOKEN ||
  JSON.parse(readFileSync(".runtime/host-admin.json", "utf8")).token;
const auth = (key) => ({
  Authorization: `Bearer ${key}`,
  ...(process.env.AGENTIX_SITES_BYPASS
    ? {
        "OAI-Sites-Authorization": "Bearer " + process.env.AGENTIX_SITES_BYPASS,
      }
    : {}),
});
test.beforeEach(async ({ page }) => {
  if (process.env.AGENTIX_SITES_BYPASS) {
    const origin = new URL(process.env.AGENTIX_BROWSER_URL).origin;
    await page.route(origin + "/**", async (route) => {
      const response = await route.fetch({
        maxRedirects: 0,
        headers: {
          ...route.request().headers(),
          "OAI-Sites-Authorization":
            "Bearer " + process.env.AGENTIX_SITES_BYPASS,
        },
      });
      await route.fulfill({ response });
    });
  }
});
const idem = (key) => ({
  ...auth(key),
  "Idempotency-Key": crypto.randomUUID(),
});
async function login(page, key) {
  await page.goto("/");
  await page.getByLabel("Agentix access key").fill(key);
  await page.getByRole("button", { name: "Enter workspace" }).click();
  await expect(page.locator("aside.sidebar")).toBeVisible();
}
async function signout(page) {
  await page.getByRole("button", { name: "Sign out" }).click();
  await expect(page.getByLabel("Agentix access key")).toBeVisible();
}
async function modalSubmit(page, label) {
  await page
    .locator("dialog")
    .getByRole("button", { name: label, exact: true })
    .click();
  await expect(page.locator("dialog")).not.toBeVisible();
}
test("creator, agent and admin complete project matching, work review, earnings and AI posting", async ({
  page,
  request,
}) => {
  const errors = [];
  const cacheViolations = [];
  let privateResponses = 0;
  page.on("response", (response) => {
    if (new URL(response.url()).pathname.startsWith("/v1/")) {
      privateResponses++;
      if (response.headers()["cache-control"] !== "no-store")
        cacheViolations.push(new URL(response.url()).pathname);
    }
  });
  page.on("pageerror", (err) => errors.push(err.message));
  await login(page, admin);
  await expect(
    page.getByRole("heading", { name: "Platform overview" }),
  ).toBeVisible();
  await page.getByRole("button", { name: "+ Create account" }).click();
  const name = "Browser creator " + Date.now();
  await page.getByLabel("Creator name").fill(name);
  await page
    .locator("dialog")
    .getByRole("button", { name: "Create account", exact: true })
    .click();
  await expect(page.locator(".key-box")).toBeVisible();
  let creator = (await page.locator(".key-box").textContent()).trim();
  await page.getByRole("button", { name: "Saved my key" }).click();
  const row = page.getByRole("row").filter({ hasText: name });
  await row.getByRole("button", { name: "Fund test credits" }).click();
  await page.getByLabel("Test credit amount").fill("1000");
  await modalSubmit(page, "Issue credits");
  await expect(row).toContainText("1,000");
  const previousCreatorKey = creator;
  await row.getByRole("button", { name: "Replace creator key", exact: true }).click();
  await expect(page.locator("dialog")).toContainText("suspension status are preserved");
  await page.getByRole("button", { name: "Replace creator key now", exact: true }).click();
  await expect(page.locator(".key-box")).toBeVisible();
  creator = (await page.locator(".key-box").textContent()).trim();
  expect(creator).not.toBe(previousCreatorKey);
  expect((await request.get("/v1/session", { headers: auth(previousCreatorKey) })).status()).toBe(401);
  await page.getByRole("button", { name: "Saved my key" }).click();
  await expect(row).toContainText("1,000");
  await signout(page);
  await login(page, creator);
  await page.getByRole("button", { name: "Review exhausted work" }).click();
  await expect(page.locator("dialog")).toContainText(
    "No exhausted assignments on this page.",
  );
  await page.getByRole("button", { name: "Close recovery queue" }).click();
  await page.route("**/v1/creator/recovery?*", (route) =>
    route.fulfill({
      status: 503,
      headers: { "Cache-Control": "no-store" },
      json: { detail: "Unavailable" },
    }),
  );
  await page.getByRole("button", { name: "Review exhausted work" }).click();
  await expect(page.getByRole("alert")).toContainText(
    "Recovery queue could not be loaded",
  );
  await page.unroute("**/v1/creator/recovery?*");
  await page.getByRole("button", { name: "Retry recovery" }).click();
  await expect(page.locator("dialog")).toContainText(
    "No exhausted assignments on this page.",
  );
  await page.getByRole("button", { name: "Close recovery queue" }).click();

  await page.getByRole("button", { name: "+ Add", exact: true }).click();
  const workerName = "Cross-framework coder " + Date.now();
  await page.getByLabel("Agent name").fill(workerName);
  await page.getByLabel("Framework / provider").fill("openai-agents-sdk");
  await page
    .getByLabel("Owner-managed HTTPS endpoint")
    .fill("https://owner.example/agent");
  await page.getByLabel("Concurrent task capacity").fill("5");
  await page
    .locator("dialog")
    .getByRole("button", { name: "Register agent", exact: true })
    .click();
  await expect(page.locator(".key-box")).toBeVisible();
  let worker = (await page.locator(".key-box").textContent()).trim();
  await page.getByRole("button", { name: "Saved my key" }).click();
  await expect(page.locator(".key-box")).toHaveCount(0);
  await page.getByRole("button", { name: "Replace key", exact: true }).click();
  await page.getByRole("button", { name: "Cancel", exact: true }).click();
  expect(
    (await request.get("/v1/session", { headers: auth(worker) })).status(),
  ).toBe(200);
  await page.getByRole("button", { name: "Replace key", exact: true }).click();
  await page
    .getByRole("button", { name: "Replace key now", exact: true })
    .click();
  await expect(page.locator(".key-box")).toBeVisible();
  const oldWorker = worker;
  worker = (await page.locator(".key-box").textContent()).trim();
  expect(worker).not.toBe(oldWorker);
  await page.getByRole("button", { name: "Saved my key" }).click();
  await expect(page.locator(".key-box")).toHaveCount(0);
  expect(
    (await request.get("/v1/session", { headers: auth(oldWorker) })).status(),
  ).toBe(401);
  expect(
    (await request.get("/v1/session", { headers: auth(worker) })).status(),
  ).toBe(200);
  await page.getByRole("button", { name: "Skills", exact: true }).click();
  await page.getByLabel("Skill tag").fill("coding");
  await page
    .getByLabel("What is this agent good at?")
    .fill("Explain code and create implementation plans");
  await modalSubmit(page, "Save skill");
  await page.getByRole("button", { name: "Activate", exact: true }).click();
  await expect(page.locator(".agent-card")).toContainText("Available");
  await page.getByRole("button", { name: "Allowance", exact: true }).click();
  await page.getByLabel("Total delegated allowance").fill("300");
  await modalSubmit(page, "Set allowance");
  await page.getByRole("button", { name: "+ Post project" }).click();
  await page.getByLabel("Project title").fill("Ship a collaboration backend");
  await page
    .getByLabel("Describe the work")
    .fill("Write a concise code review checklist");
  await page.getByLabel("Skills needed").fill("coding");
  await page.getByLabel("Project budget").fill("200");
  await modalSubmit(page, "Post project");
  await page.getByRole("button", { name: "Find agents" }).click();
  await page
    .getByLabel("Agent · skill")
    .selectOption({ label: workerName + " · openai-agents-sdk · coding" });
  await page
    .getByLabel("Task instructions")
    .fill("Explain one benefit of automated tests in one sentence.");
  await page.getByLabel("Acceptance criteria").fill("A clear useful sentence");
  await page.getByLabel("Contribution price").fill("50");
  await modalSubmit(page, "Assign task");
  await signout(page);
  await login(page, worker);
  const inbox = await request.get("/v1/tasks?state=reserved&limit=1&offset=0", {
    headers: auth(worker),
  });
  expect(inbox.status()).toBe(200);
  expect(await inbox.json()).toHaveLength(1);
  const nextInboxPage = await request.get(
    "/v1/tasks?state=reserved&limit=1&offset=1",
    { headers: auth(worker) },
  );
  expect(await nextInboxPage.json()).toEqual([]);
  const acceptedInbox = await request.get("/v1/tasks?state=accepted&limit=1", {
    headers: auth(worker),
  });
  expect(await acceptedInbox.json()).toEqual([]);
  await expect(
    page.getByRole("heading", { name: "Agent workspace" }),
  ).toBeVisible();
  // Display-only exhaustion injection; backend tests execute five real attempts.
  const taskRoute = /\/v1\/tasks\/[^/?]+$/;
  await page.route(taskRoute, async (route) => {
    const response = await route.fetch();
    const task = await response.json();
    await route.fulfill({
      response,
      json: {
        ...task,
        state: "running",
        attempts: 5,
        attempt_limit: 5,
        lease_expires_at: new Date(Date.now() - 1000).toISOString(),
      },
    });
  });
  await page.getByRole("button", { name: "Open", exact: true }).click();
  await expect(page.locator("dialog").getByRole("alert")).toContainText(
    "Execution attempt limit reached",
  );
  await expect(
    page.getByRole("button", { name: "Start manually", exact: true }),
  ).toHaveCount(0);
  await page.getByRole("button", { name: "×", exact: true }).click();
  await page.unroute(taskRoute);
  await page.getByRole("button", { name: "Open", exact: true }).click();
  await expect(
    page.getByRole("button", { name: "Replace key", exact: true }),
  ).toHaveCount(0);
  await page.getByRole("button", { name: "Start manually" }).click();
  await expect(
    page.getByRole("region", { name: "Execution history" }),
  ).toContainText("Work claimed");
  const submission = page.getByRole("button", {
    name: "Submit deliverable",
    exact: true,
  });
  const activeTaskId = await submission.getAttribute("data-id");
  const executionToken = await page.evaluate(
    (id) => sessionStorage.getItem(`lease-${id}`),
    activeTaskId,
  );
  // Real API events exercise both history pages without external inference.
  for (let i = 0; i < 100; i++) {
    expect(
      (
        await request.post(`/v1/tasks/${activeTaskId}/heartbeat`, {
          headers: { ...auth(worker), "X-Execution-Token": executionToken },
          data: {},
        })
      ).status(),
    ).toBe(200);
  }
  await page.getByRole("button", { name: "×", exact: true }).click();
  await page.getByRole("button", { name: "Open", exact: true }).click();
  await expect(page.locator("#task-history-list li")).toHaveCount(100);
  await page
    .getByRole("button", { name: "Load more events", exact: true })
    .click();
  await expect(page.locator("#task-history-list li")).toHaveCount(102);
  await expect(
    page.getByRole("button", { name: "Load more events", exact: true }),
  ).toHaveCount(0);
  await page.getByRole("button", { name: "Submit deliverable" }).click();
  await page.getByLabel("Completed work").fill("界".repeat(40000));
  await page
    .locator("dialog")
    .getByRole("button", { name: "Submit for review", exact: true })
    .click();
  await expect(page.locator("dialog .error-message")).toContainText(
    "100,000 bytes",
  );
  await expect(page.getByLabel("Completed work")).toHaveValue(
    "界".repeat(40000),
  );
  await page
    .getByLabel("Completed work")
    .fill("Automated tests make regression errors visible before release.");
  await modalSubmit(page, "Submit for review");
  await expect(page.getByText(/1 slots occupied/)).toBeVisible();
  await expect(
    page.getByRole("cell", { name: "submitted", exact: true }),
  ).toBeVisible();
  await signout(page);
  await login(page, creator);
  await expect(page.getByText(/1 slots occupied/)).toBeVisible();
  await page.getByRole("button", { name: "Open", exact: true }).click();
  await expect(
    page.getByRole("region", { name: "Execution history" }),
  ).toContainText("Work reserved");
  await page.getByRole("button", { name: "Accept & pay credits" }).click();
  await expect(page.locator("dialog")).not.toBeVisible();
  await expect(page.getByText(/0 slots occupied/)).toBeVisible();
  await expect(
    page.locator(".stat").filter({ hasText: "Agent earnings" }),
  ).toContainText("50");
  await page
    .getByRole("button", { name: "Close project", exact: true })
    .click();
  await page
    .getByRole("button", { name: "Close & return credits", exact: true })
    .click();
  await expect(page.locator("dialog")).not.toBeVisible();
  await expect(page.locator(".project-card")).toContainText("Closed");
  await expect(page.locator(".project-card")).toContainText(
    "150 credits returned",
  );
  await expect(
    page.locator(".stat").filter({ hasText: "Spendable credits" }),
  ).toContainText("950");
  await expect(
    page.getByRole("button", { name: "Close project", exact: true }),
  ).toHaveCount(0);
  await page.getByRole("button", { name: "View credit history" }).click();
  await expect(
    page.getByRole("table", { name: "Credit movements" }),
  ).toBeVisible();
  await expect(page.locator("dialog tbody tr")).toHaveCount(5);
  await expect(page.locator("dialog")).not.toContainText("Date unavailable");
  const firstCreditPage = await page.locator("dialog tbody").innerText();
  await page.getByRole("button", { name: "Next page", exact: true }).click();
  await expect(page.locator("dialog")).toContainText("Page 2");
  await expect(page.locator("dialog tbody tr")).toHaveCount(4);
  const movementText =
    firstCreditPage + (await page.locator("dialog tbody").innerText());
  for (const label of [
    "Test funding",
    "Project funding",
    "Assignment reserved",
    "Work accepted",
    "Project refund",
  ])
    expect(movementText).toContain(label);
  await page
    .getByRole("button", { name: "Previous page", exact: true })
    .click();
  await expect
    .poll(() => page.locator("dialog tbody").innerText())
    .toBe(firstCreditPage);
  await page.getByRole("button", { name: "Close credit history" }).click();
  await page.route("**/v1/wallet/entries?*", (route) =>
    route.fulfill({
      status: 503,
      headers: { "Cache-Control": "no-store" },
      json: { detail: "Unavailable" },
    }),
  );
  await page.getByRole("button", { name: "View credit history" }).click();
  await expect(page.getByRole("alert")).toContainText(
    "Credit history could not be loaded",
  );
  await page.unroute("**/v1/wallet/entries?*");
  await page.getByRole("button", { name: "Retry history" }).click();
  await expect(
    page.getByRole("table", { name: "Credit movements" }),
  ).toBeVisible();
  await page.getByRole("button", { name: "Close credit history" }).click();
  // Credentials cannot cross into superadmin controls.
  expect(
    (
      await request.get("/v1/admin/overview", { headers: auth(worker) })
    ).status(),
  ).toBe(403);
  await signout(page);
  await login(page, worker);
  await page.getByRole("button", { name: "+ Post project" }).click();
  await page
    .getByLabel("Project title")
    .fill("AI requests a marketing partner");
  await page.getByLabel("Describe the work").fill("Develop a launch tagline");
  await page.getByLabel("Skills needed").fill("marketing");
  await page.getByLabel("Project budget").fill("100");
  await modalSubmit(page, "Post project");
  await expect(
    page.locator(".stat").filter({ hasText: "Project allowance" }),
  ).toContainText("200");
  await page.getByRole("button", { name: "Projects", exact: true }).click();
  await expect(page.locator(".project-card")).toContainText("AI posted");
  await page.setViewportSize({ width: 390, height: 844 });
  await expect(page.locator("body")).toBeVisible();
  expect(
    await page.evaluate(
      () => document.documentElement.scrollWidth <= innerWidth,
    ),
  ).toBe(true);
  await page.screenshot({ path: ".runtime/agent-mobile.png", fullPage: true });
  await signout(page);
  await page.setViewportSize({ width: 1440, height: 1000 });
  await login(page, admin);
  await page.screenshot({
    path: ".runtime/admin-dashboard.png",
    fullPage: true,
  });
  const ledger = await request.get("/v1/admin/overview", {
    headers: auth(admin),
  });
  const wallet = await (
    await request.get("/v1/wallet", { headers: auth(creator) })
  ).json();
  const journalEntries = [];
  for (let offset = 0; offset < 100; offset += 2) {
    const response = await request.get(
      `/v1/wallet/entries?limit=2&offset=${offset}`,
      { headers: auth(creator) },
    );
    expect(response.status()).toBe(200);
    const batch = await response.json();
    expect(batch.length).toBeLessThanOrEqual(2);
    journalEntries.push(...batch);
    if (batch.length < 2) break;
  }
  expect(journalEntries.length).toBeGreaterThan(2);
  expect(new Set(journalEntries.map((e) => e.id)).size).toBe(
    journalEntries.length,
  );
  for (const entry of journalEntries) {
    expect(typeof entry.journal_id).toBe("string");
    expect(wallet.accounts.some((a) => a.id === entry.account_id)).toBe(true);
  }
  expect(journalEntries.reduce((sum, e) => sum + e.amount, 0)).toBe(
    wallet.accounts.reduce((sum, a) => sum + a.balance, 0),
  );
  const ledgerData = await ledger.json();
  expect(ledgerData.ledger_balance).toBe(0);
  const capacityPage = await request.get("/v1/admin/capacity?limit=5&offset=0", { headers: auth(admin) });
  expect(capacityPage.status()).toBe(200);
  expect(capacityPage.headers()["cache-control"]).toBe("no-store");
  expect(await capacityPage.json()).toEqual([]);
  expect((await request.get("/v1/admin/capacity", { headers: auth(creator) })).status()).toBe(403);
  expect(ledgerData.ledger_check).toEqual({
    healthy: true,
    mismatched_accounts: 0,
    invalid_journals: 0,
  });
  await expect(
    page.getByRole("status", { name: "Ledger reconciliation" }),
  ).toContainText("Healthy: account balances match journal entries.");
  expect(Object.keys(ledgerData.execution_health).sort()).toEqual(
    ["active_leases", "exhausted", "retryable_expired"],
  );
  await expect(page.getByRole("status", { name: "Execution health", exact: true }))
    .toContainText(`${ledgerData.execution_health.exhausted} exhausted`);
  expect(ledgerData.capacity_check).toEqual({ healthy: true, overcommitted_agents: 0, excess_assignments: 0, agents: [], truncated: false });
  await expect(page.getByRole("status", { name: "Capacity check", exact: true }))
    .toHaveText("Healthy: assignments fit configured agent capacity.");
  // Exercise the warning display without corrupting the running test database.
  await page.route("**/v1/admin/overview", async (route) => {
    const response = await route.fetch();
    const body = await response.json();
    body.capacity_check = { healthy: false, overcommitted_agents: 2, excess_assignments: 3,
      agents: [{ agent_id: "agent-example", agent_name: "<img src=x onerror=alert(1)>",
        owner_id: "creator-example", capacity: 1, occupied_slots: 3, excess_assignments: 2 }], truncated: false };
    body.execution_health = { active_leases: 3, retryable_expired: 2, exhausted: 1 };
    body.ledger_check = {
      healthy: false,
      mismatched_accounts: 2,
      invalid_journals: 1,
    };
    await route.fulfill({ response, json: body });
  });
  await page.getByRole("button", { name: "Refresh", exact: true }).click();
  await expect(
    page.getByRole("status", { name: "Ledger reconciliation" }),
  ).toContainText("Review required: 2 account mismatches; 1 invalid journals.");
  await expect(page.getByRole("status", { name: "Execution health", exact: true }))
    .toHaveText("3 active leases · 2 expired and retryable · 1 exhausted");
  await expect(page.getByRole("status", { name: "Capacity check", exact: true }))
    .toHaveText("Review required: 2 overcommitted agents; 3 excess assignments.");
  const capacityDetails = page.getByRole("region", { name: "Overcommitted agents", exact: true });
  await expect(capacityDetails).toContainText("<img src=x onerror=alert(1)>");
  await expect(capacityDetails).toContainText("Creator: creator-example");
  await expect(capacityDetails).toContainText("3 occupied / 1 capacity · 2 excess");
  await expect(capacityDetails.locator("img")).toHaveCount(0);
  expect(errors).toEqual([]);
  expect(privateResponses).toBeGreaterThan(10);
  expect(cacheViolations).toEqual([]);
});
test("real free API completes a task and credits go to the creator", async ({
  page,
  request,
}) => {
  test.skip(
    !!process.env.CI && !process.env.AGENTIX_RUN_FREE_API_CHECK,
    "Live free provider check is opt-in in CI",
  );
  const creatorResponse = await request.post("/v1/admin/owners", {
    headers: auth(admin),
    data: { name: "Free API validation " + Date.now() },
  });
  expect(creatorResponse.status()).toBe(201);
  const owner = await creatorResponse.json();
  const funded = await request.post(
    `/v1/admin/owners/${owner.id}/test-funding`,
    { headers: idem(admin), data: { amount: 500 } },
  );
  expect(funded.ok()).toBe(true);
  const agentResponse = await request.post("/v1/agents", {
    headers: auth(owner.api_key),
    data: {
      name: "Free marketing worker",
      framework: "pollinations-free",
      endpoint: "https://owner.example/agent",
    },
  });
  const agent = await agentResponse.json();
  await request.patch(`/v1/agents/${agent.id}/availability`, {
    headers: auth(agent.api_key),
    data: { available: true },
  });
  const skill = await (
    await request.post(`/v1/agents/${agent.id}/skills`, {
      headers: auth(owner.api_key),
      data: {
        slug: "marketing",
        version: "1",
        description: "Create a tagline",
      },
    })
  ).json();
  const project = await (
    await request.post("/v1/projects", {
      headers: idem(owner.api_key),
      data: {
        title: "Free model launch copy",
        budget: 100,
        published: true,
        required_skills: ["marketing"],
      },
    })
  ).json();
  const task = await (
    await request.post(`/v1/projects/${project.id}/tasks`, {
      headers: idem(owner.api_key),
      data: {
        agent_id: agent.id,
        skill_id: skill.id,
        instructions:
          "Write one short original marketing tagline for Agentix, a platform where independent AI agents collaborate.",
        acceptance_criteria: "A single concise tagline",
        price: 40,
      },
    })
  ).json();
  await login(page, agent.api_key);
  await page.getByRole("button", { name: "Open", exact: true }).click();
  await page.getByRole("button", { name: "Run free AI" }).click();
  await expect(page.locator(".artifact")).toBeVisible({ timeout: 120000 });
  expect(
    (await page.locator(".artifact").textContent()).length,
  ).toBeGreaterThan(5);
  await page.getByRole("button", { name: "×", exact: true }).click();
  await signout(page);
  await login(page, owner.api_key);
  await page.getByRole("button", { name: "Open", exact: true }).click();
  await expect(
    page.getByRole("region", { name: "Execution history" }),
  ).toContainText("Work reserved");
  await page.getByRole("button", { name: "Accept & pay credits" }).click();
  await expect(page.locator("dialog")).not.toBeVisible();
  await expect(
    page.locator(".stat").filter({ hasText: "Agent earnings" }),
  ).toContainText("40");
  // Replay does not create a second settlement.
  expect(
    (
      await request.post(`/v1/tasks/${task.id}/accept`, {
        headers: auth(owner.api_key),
      })
    ).ok(),
  ).toBe(true);
  const wallet = await (
    await request.get("/v1/wallet", { headers: auth(owner.api_key) })
  ).json();
  expect(wallet.earnings).toBe(40);
  await page.screenshot({
    path: ".runtime/creator-dashboard.png",
    fullPage: true,
  });
});

test("expired execution can be cancelled and credits returned by its creator", async ({
  page,
  request,
}) => {
  const creatorResponse = await request.post("/v1/admin/owners", {
    headers: auth(admin),
    data: { name: "Expired lease validation " + Date.now() },
  });
  expect(creatorResponse.status()).toBe(201);
  const owner = await creatorResponse.json();
  const funded = await request.post(
    `/v1/admin/owners/${owner.id}/test-funding`,
    { headers: idem(admin), data: { amount: 500 } },
  );
  expect(funded.ok()).toBe(true);
  const agentResponse = await request.post("/v1/agents", {
    headers: auth(owner.api_key),
    data: {
      name: "Free marketing worker",
      framework: "owner-managed",
      endpoint: "https://owner.example/agent",
    },
  });
  const agent = await agentResponse.json();
  await request.patch(`/v1/agents/${agent.id}/availability`, {
    headers: auth(agent.api_key),
    data: { available: true },
  });
  const skill = await (
    await request.post(`/v1/agents/${agent.id}/skills`, {
      headers: auth(owner.api_key),
      data: {
        slug: "marketing",
        version: "1",
        description: "Create a tagline",
      },
    })
  ).json();
  const project = await (
    await request.post("/v1/projects", {
      headers: idem(owner.api_key),
      data: {
        title: "Free model launch copy",
        budget: 100,
        published: true,
        required_skills: ["marketing"],
      },
    })
  ).json();
  const task = await (
    await request.post(`/v1/projects/${project.id}/tasks`, {
      headers: idem(owner.api_key),
      data: {
        agent_id: agent.id,
        skill_id: skill.id,
        instructions:
          "Write one short original marketing tagline for Agentix, a platform where independent AI agents collaborate.",
        acceptance_criteria: "A single concise tagline",
        price: 40,
      },
    })
  ).json();

  const token = crypto.randomUUID();
  const started = await request.post(`/v1/tasks/${task.id}/start`, {
    headers: { ...auth(agent.api_key), "X-Execution-Token": token },
    data: { lease_seconds: 30 },
  });
  expect(started.status()).toBe(200);
  expect(
    (
      await request.post(`/v1/tasks/${task.id}/cancel`, {
        headers: auth(owner.api_key),
      })
    ).status(),
  ).toBe(409);
  await login(page, owner.api_key);
  await expect
    .poll(
      async () => {
        const response = await request.get(`/v1/tasks/${task.id}`, {
          headers: auth(owner.api_key),
        });
        return (
          Date.parse((await response.json()).lease_expires_at) <= Date.now()
        );
      },
      { timeout: 40000, intervals: [1000] },
    )
    .toBe(true);
  // Backend tests build five attempts; this injection exercises the populated queue UI
  // while cancellation still hits the real expired assignment and ledger.
  const expiredTask = await (
    await request.get(`/v1/tasks/${task.id}`, { headers: auth(owner.api_key) })
  ).json();
  let failFiltered = true;
  await page.route("**/v1/creator/recovery?*", (route) => {
    if (
      new URL(route.request().url()).searchParams.has("project_id") &&
      failFiltered
    ) {
      failFiltered = false;
      return route.fulfill({
        status: 503,
        headers: { "Cache-Control": "no-store" },
        json: { detail: "Unavailable" },
      });
    }
    return route.fulfill({
      status: 200,
      headers: { "Cache-Control": "no-store" },
      json: [
        {
          ...expiredTask,
          attempts: 5,
          attempt_limit: 5,
          project_title:
            'Recovery <img src=x onerror="window.badRecovery=true">',
          agent_name: "Worker & tools",
        },
      ],
    });
  });
  await page.getByRole("button", { name: "Review exhausted work" }).click();
  await expect(page.locator("dialog")).toContainText("5 attempts");
  await expect(page.locator("dialog")).toContainText("Worker & tools");
  await expect(page.locator("dialog h3")).toContainText("Recovery <img");
  await expect(page.locator("dialog img")).toHaveCount(0);
  await page.getByRole("button", { name: "Only this project" }).click();
  await expect(page.getByRole("alert")).toContainText(
    "Recovery queue could not be loaded",
  );
  const filterRequest = page.waitForRequest(
    (r) =>
      r.url().includes("/v1/creator/recovery?") &&
      new URL(r.url()).searchParams.get("project_id") === project.id,
  );
  await page.getByRole("button", { name: "Retry recovery" }).click();
  await filterRequest;
  await expect(page.locator("dialog")).toContainText("Showing one project");
  await page.getByRole("button", { name: "All projects", exact: true }).click();
  await expect(
    page.getByRole("button", { name: "Only this project" }),
  ).toBeVisible();

  await page
    .getByRole("button", { name: "Cancel assignment", exact: true })
    .click();
  await expect(page.locator("dialog")).not.toBeVisible();
  await page.unroute("**/v1/creator/recovery?*");
  const result = await (
    await request.get(`/v1/tasks/${task.id}`, { headers: auth(owner.api_key) })
  ).json();
  expect(result.state).toBe("cancelled");
  const wallet = await (
    await request.get("/v1/wallet", { headers: auth(owner.api_key) })
  ).json();
  expect(wallet.earnings).toBe(0);
  expect(wallet.accounts.find((a) => a.kind === "project").balance).toBe(100);
  expect(
    (
      await request.post(`/v1/tasks/${task.id}/submit`, {
        headers: { ...auth(agent.api_key), "X-Execution-Token": token },
        data: { artifact: { text: "late result" } },
      })
    ).status(),
  ).toBe(409);
});
