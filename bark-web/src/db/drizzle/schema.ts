import { relations } from "drizzle-orm";
import {
	boolean,
	foreignKey,
	index,
	json,
	pgTable,
	text,
	timestamp,
	uniqueIndex,
	varchar,
	vector,
} from "drizzle-orm/pg-core";

export const agentPosts = pgTable("agent_posts", {
	id: varchar().primaryKey().notNull(),
	agentId: varchar("agent_id"),
	content: text(),
	embedding: vector({ dimensions: 1536 }),
	createdAt: timestamp("created_at", { mode: "string" }),
});

export const conversations = pgTable(
	"conversations",
	{
		id: varchar().primaryKey().notNull(),
		userId: varchar("user_id"),
		createdAt: timestamp("created_at", { mode: "string" }),
	},
	(table) => [
		foreignKey({
			columns: [table.userId],
			foreignColumns: [users.id],
			name: "conversations_user_id_fkey",
		}),
	],
);

export const messages = pgTable(
	"messages",
	{
		id: varchar().primaryKey().notNull(),
		conversationId: varchar("conversation_id"),
		role: varchar(),
		content: text(),
		createdAt: timestamp("created_at", { mode: "string" }),
	},
	(table) => [
		foreignKey({
			columns: [table.conversationId],
			foreignColumns: [conversations.id],
			name: "messages_conversation_id_fkey",
		}),
	],
);

export const users = pgTable(
	"users",
	{
		id: varchar().primaryKey().notNull(),
		email: varchar(),
		name: varchar(),
		profileData: json("profile_data"),
	},
	(table) => [
		uniqueIndex("ix_users_email").using(
			"btree",
			table.email.asc().nullsLast().op("text_ops"),
		),
	],
);

export const apiLogs = pgTable(
	"api_logs",
	{
		id: varchar().primaryKey().notNull(),
		conversationId: varchar("conversation_id"),
		eventType: varchar("event_type"),
		payload: text(),
		createdAt: timestamp("created_at", { mode: "string" }),
	},
	(table) => [
		foreignKey({
			columns: [table.conversationId],
			foreignColumns: [conversations.id],
			name: "api_logs_conversation_id_fkey",
		}),
	],
);

export const contextSummaries = pgTable(
	"context_summaries",
	{
		id: varchar().primaryKey().notNull(),
		conversationId: varchar("conversation_id"),
		summary: text(),
		messagesSummarized: varchar("messages_summarized"),
		createdAt: timestamp("created_at", { mode: "string" }),
	},
	(table) => [
		foreignKey({
			columns: [table.conversationId],
			foreignColumns: [conversations.id],
			name: "context_summaries_conversation_id_fkey",
		}),
	],
);

export const tools = pgTable("tools", {
	id: varchar().primaryKey().notNull(),
	name: varchar().unique().notNull(),
	description: text().notNull(),
	toolType: varchar("tool_type").notNull(), // 'native', 'python', 'mcp'
	content: text().notNull(),
	createdAt: timestamp("created_at", { mode: "string" }).defaultNow().notNull(),
	updatedAt: timestamp("updated_at", { mode: "string" }).defaultNow().notNull(),
});
export const user = pgTable("user", {
	id: text("id").primaryKey(),
	name: text("name").notNull(),
	email: text("email").notNull().unique(),
	emailVerified: boolean("email_verified").default(false).notNull(),
	image: text("image"),
	createdAt: timestamp("created_at").defaultNow().notNull(),
	updatedAt: timestamp("updated_at")
		.defaultNow()
		.$onUpdate(() => /* @__PURE__ */ new Date())
		.notNull(),
});

export const session = pgTable(
	"session",
	{
		id: text("id").primaryKey(),
		expiresAt: timestamp("expires_at").notNull(),
		token: text("token").notNull().unique(),
		createdAt: timestamp("created_at").defaultNow().notNull(),
		updatedAt: timestamp("updated_at")
			.$onUpdate(() => /* @__PURE__ */ new Date())
			.notNull(),
		ipAddress: text("ip_address"),
		userAgent: text("user_agent"),
		userId: text("user_id")
			.notNull()
			.references(() => user.id, { onDelete: "cascade" }),
	},
	(table) => [index("session_userId_idx").on(table.userId)],
);

export const account = pgTable(
	"account",
	{
		id: text("id").primaryKey(),
		accountId: text("account_id").notNull(),
		providerId: text("provider_id").notNull(),
		userId: text("user_id")
			.notNull()
			.references(() => user.id, { onDelete: "cascade" }),
		accessToken: text("access_token"),
		refreshToken: text("refresh_token"),
		idToken: text("id_token"),
		accessTokenExpiresAt: timestamp("access_token_expires_at"),
		refreshTokenExpiresAt: timestamp("refresh_token_expires_at"),
		scope: text("scope"),
		password: text("password"),
		createdAt: timestamp("created_at").defaultNow().notNull(),
		updatedAt: timestamp("updated_at")
			.$onUpdate(() => /* @__PURE__ */ new Date())
			.notNull(),
	},
	(table) => [index("account_userId_idx").on(table.userId)],
);

export const verification = pgTable(
	"verification",
	{
		id: text("id").primaryKey(),
		identifier: text("identifier").notNull(),
		value: text("value").notNull(),
		expiresAt: timestamp("expires_at").notNull(),
		createdAt: timestamp("created_at").defaultNow().notNull(),
		updatedAt: timestamp("updated_at")
			.defaultNow()
			.$onUpdate(() => /* @__PURE__ */ new Date())
			.notNull(),
	},
	(table) => [index("verification_identifier_idx").on(table.identifier)],
);

export const userRelations = relations(user, ({ many }) => ({
	sessions: many(session),
	accounts: many(account),
}));

export const sessionRelations = relations(session, ({ one }) => ({
	user: one(user, {
		fields: [session.userId],
		references: [user.id],
	}),
}));

export const accountRelations = relations(account, ({ one }) => ({
	user: one(user, {
		fields: [account.userId],
		references: [user.id],
	}),
}));

export const roles = pgTable("roles", {
	id: varchar().primaryKey().notNull(),
	name: varchar().unique().notNull(),
	description: text(),
	createdAt: timestamp("created_at", { mode: "string" }).defaultNow().notNull(),
});

export const userRoles = pgTable(
	"user_roles",
	{
		id: varchar().primaryKey().notNull(),
		userId: text("user_id")
			.notNull()
			.references(() => user.id, { onDelete: "cascade" }),
		roleId: varchar("role_id")
			.notNull()
			.references(() => roles.id, { onDelete: "cascade" }),
		createdAt: timestamp("created_at", { mode: "string" })
			.defaultNow()
			.notNull(),
	},
	(table) => [
		index("user_roles_userId_idx").on(table.userId),
		index("user_roles_roleId_idx").on(table.roleId),
	],
);

export const surfaceCredentials = pgTable(
	"surface_credentials",
	{
		id: varchar().primaryKey().notNull(),
		userId: text("user_id")
			.notNull()
			.references(() => user.id, { onDelete: "cascade" }),
		surface: varchar().notNull(),
		token: text().notNull(),
		createdAt: timestamp("created_at", { mode: "string" })
			.defaultNow()
			.notNull(),
		updatedAt: timestamp("updated_at", { mode: "string" })
			.defaultNow()
			.notNull(),
	},
	(table) => [
		index("surface_credentials_userId_idx").on(table.userId),
		index("surface_credentials_surface_idx").on(table.surface),
	],
);

export const rolesRelations = relations(roles, ({ many }) => ({
	users: many(userRoles),
}));

export const userRolesRelations = relations(userRoles, ({ one }) => ({
	user: one(user, {
		fields: [userRoles.userId],
		references: [user.id],
	}),
	role: one(roles, {
		fields: [userRoles.roleId],
		references: [roles.id],
	}),
}));

export const surfaceCredentialsRelations = relations(
	surfaceCredentials,
	({ one }) => ({
		user: one(user, {
			fields: [surfaceCredentials.userId],
			references: [user.id],
		}),
	}),
);
