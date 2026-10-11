// Portable local D1 adapter for integration/browser checks (production uses native D1).
import { DatabaseSync } from "node:sqlite";
import { createServer } from "node:http";
import { readFileSync, existsSync } from "node:fs";
import { webcrypto } from "node:crypto";
import worker from "../dist/server/index.js";
const path = process.env.D1_LOCAL_FILE || "../.runtime/hosted.db";
const fresh = !existsSync(path),
  sqlite = new DatabaseSync(path);
sqlite.exec("PRAGMA foreign_keys=ON");
if (fresh) {
  const journal = JSON.parse(
    readFileSync("drizzle/meta/_journal.json", "utf8"),
  );
  for (const entry of journal.entries)
    sqlite.exec(readFileSync("drizzle/" + entry.tag + ".sql", "utf8"));
}
class Prepared {
  constructor(sql, args = []) {
    this.sql = sql;
    this.args = args;
  }
  bind(...args) {
    return new Prepared(this.sql, args);
  }
  async all() {
    return { results: sqlite.prepare(this.sql).all(...this.args) };
  }
  async first() {
    return sqlite.prepare(this.sql).get(...this.args) || null;
  }
  async run() {
    const v = sqlite.prepare(this.sql).run(...this.args);
    return { meta: { changes: Number(v.changes) } };
  }
}
export const DB = {
  prepare: (sql) => new Prepared(sql),
  batch: async (statements) => {
    sqlite.exec("BEGIN IMMEDIATE");
    try {
      const result = [];
      for (const p of statements) {
        if (/^\s*SELECT/i.test(p.sql))
          result.push({ results: sqlite.prepare(p.sql).all(...p.args) });
        else {
          const v = sqlite.prepare(p.sql).run(...p.args);
          result.push({ meta: { changes: Number(v.changes) } });
        }
      }
      sqlite.exec("COMMIT");
      return result;
    } catch (error) {
      sqlite.exec("ROLLBACK");
      throw error;
    }
  },
};
const env = {
  DB,
  ADMIN_HASH: process.env.ADMIN_HASH,
  OWNER_PRIVATE: "1",
  ENABLE_TEST_FUNDING: "1",
  ENABLE_FREE_MODEL: "1",
};
const port = Number(process.env.PORT || 8001);
createServer(async (req, res) => {
  try {
    const chunks = [];
    for await (const chunk of req) chunks.push(chunk);
    const body = Buffer.concat(chunks);
    const r = new Request("http://127.0.0.1:" + port + req.url, {
      method: req.method,
      headers: req.headers,
      ...(body.length ? { body } : {}),
    });
    const result = await worker.fetch(r, env);
    res.writeHead(result.status, Object.fromEntries(result.headers));
    res.end(Buffer.from(await result.arrayBuffer()));
  } catch (error) {
    console.error(error);
    res.writeHead(500);
    res.end("Internal error");
  }
}).listen(port, "127.0.0.1", () =>
  console.log("Agentix local hosted preview http://127.0.0.1:" + port),
);
