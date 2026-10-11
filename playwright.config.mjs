import { defineConfig } from "@playwright/test";
export default defineConfig({
  testDir: "tests/browser",
  timeout: 180000,
  workers: 1,
  use: {
    baseURL: process.env.AGENTIX_BROWSER_URL || "http://127.0.0.1:8001",
    headless: true,
    ...(process.env.AGENTIX_SITES_BYPASS && process.env.HTTPS_PROXY
      ? { proxy: { server: process.env.HTTPS_PROXY } }
      : {}),
    actionTimeout: 20000,
    navigationTimeout: 20000,
  },
  reporter: "list",
});
