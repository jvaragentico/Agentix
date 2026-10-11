CREATE TABLE `balances` (
	`id` text PRIMARY KEY NOT NULL,
	`kind` text NOT NULL,
	`owner` text,
	`balance` integer NOT NULL,
	CONSTRAINT "nonnegative_credit_balance" CHECK("balances"."kind"='test_source' OR "balances"."balance">=0)
);
--> statement-breakpoint
CREATE INDEX `balances_owner` ON `balances` (`owner`);--> statement-breakpoint
CREATE TABLE `entries` (
	`id` text PRIMARY KEY NOT NULL,
	`journal` text NOT NULL,
	`account` text NOT NULL,
	`amount` integer NOT NULL,
	`reason` text NOT NULL,
	`reference` text NOT NULL,
	`created` text NOT NULL,
	FOREIGN KEY (`account`) REFERENCES `balances`(`id`) ON UPDATE no action ON DELETE no action
);
--> statement-breakpoint
CREATE INDEX `entries_account` ON `entries` (`account`);--> statement-breakpoint
CREATE TABLE `transaction_guard` (
	`ok` integer NOT NULL,
	CONSTRAINT "exactly_one_revision" CHECK("transaction_guard"."ok"=1)
);
--> statement-breakpoint
CREATE TABLE `operations` (
	`id` text PRIMARY KEY NOT NULL,
	`fingerprint` text NOT NULL,
	`response` text NOT NULL
);
--> statement-breakpoint
CREATE TABLE `records` (
	`id` text PRIMARY KEY NOT NULL,
	`type` text NOT NULL,
	`owner` text,
	`payload` text NOT NULL
);
--> statement-breakpoint
CREATE INDEX `records_type_owner` ON `records` (`type`,`owner`);--> statement-breakpoint
CREATE TABLE `revision` (
	`id` integer PRIMARY KEY NOT NULL,
	`version` integer NOT NULL
);
