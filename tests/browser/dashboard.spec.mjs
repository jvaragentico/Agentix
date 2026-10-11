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
  const creator = (await page.locator(".key-box").textContent()).trim();
  await page.getByRole("button", { name: "Saved my key" }).click();
  const row = page.getByRole("row").filter({ hasText: name });
  await row.getByRole("button", { name: "Fund test credits" }).click();
  await page.getByLabel("Test credit amount").fill("1000");
  await modalSubmit(page, "Issue credits");
  await expect(row).toContainText("1,000");
  await signout(page);
  await login(page, creator);
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
  const worker = (await page.locator(".key-box").textContent()).trim();
  await page.getByRole("button", { name: "Saved my key" }).click();
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
  await expect(
    page.getByRole("heading", { name: "Agent workspace" }),
  ).toBeVisible();
  await page.getByRole("button", { name: "Open", exact: true }).click();
  await page.getByRole("button", { name: "Start manually" }).click();
  await page.getByRole("button", { name: "Submit deliverable" }).click();
  await page
    .getByLabel("Completed work")
    .fill("Automated tests make regression errors visible before release.");
  await modalSubmit(page, "Submit for review");
  await expect(
    page.getByRole("cell", { name: "submitted", exact: true }),
  ).toBeVisible();
  await signout(page);
  await login(page, creator);
  await page.getByRole("button", { name: "Open", exact: true }).click();
  await page.getByRole("button", { name: "Accept & pay credits" }).click();
  await expect(page.locator("dialog")).not.toBeVisible();
  await expect(
    page.locator(".stat").filter({ hasText: "Agent earnings" }),
  ).toContainText("50");
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
  expect((await ledger.json()).ledger_balance).toBe(0);
  expect(errors).toEqual([]);
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
