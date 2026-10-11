import {
  sqliteTable,
  text,
  integer,
  index,
  check,
} from "drizzle-orm/sqlite-core";
import { sql } from "drizzle-orm";
export const revision = sqliteTable("revision", {
  id: integer("id").primaryKey(),
  version: integer("version").notNull(),
});
export const guard = sqliteTable(
  "transaction_guard",
  { ok: integer("ok").notNull() },
  (t) => [check("exactly_one_revision", sql`${t.ok}=1`)],
);
export const records = sqliteTable(
  "records",
  {
    id: text("id").primaryKey(),
    type: text("type").notNull(),
    owner: text("owner"),
    payload: text("payload").notNull(),
  },
  (t) => [index("records_type_owner").on(t.type, t.owner)],
);
export const balances = sqliteTable(
  "balances",
  {
    id: text("id").primaryKey(),
    kind: text("kind").notNull(),
    owner: text("owner"),
    balance: integer("balance").notNull(),
  },
  (t) => [
    check(
      "nonnegative_credit_balance",
      sql`${t.kind}='test_source' OR ${t.balance}>=0`,
    ),
    index("balances_owner").on(t.owner),
  ],
);
export const entries = sqliteTable(
  "entries",
  {
    id: text("id").primaryKey(),
    journal: text("journal").notNull(),
    account: text("account")
      .notNull()
      .references(() => balances.id),
    amount: integer("amount").notNull(),
    reason: text("reason").notNull(),
    reference: text("reference").notNull(),
    created: text("created").notNull(),
  },
  (t) => [index("entries_account").on(t.account)],
);
export const operations = sqliteTable("operations", {
  id: text("id").primaryKey(),
  fingerprint: text("fingerprint").notNull(),
  response: text("response").notNull(),
});
