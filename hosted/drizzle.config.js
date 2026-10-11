import { defineConfig } from "drizzle-kit";
export default defineConfig({
  schema: "./schema.js",
  out: "./drizzle",
  dialect: "sqlite",
});
