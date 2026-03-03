import { pgTable, varchar, text, vector, timestamp, foreignKey, uniqueIndex, json } from "drizzle-orm/pg-core"
import { sql } from "drizzle-orm"



export const agentPosts = pgTable("agent_posts", {
	id: varchar().primaryKey().notNull(),
	agentId: varchar("agent_id"),
	content: text(),
	embedding: vector({ dimensions: 1536 }),
	createdAt: timestamp("created_at", { mode: 'string' }),
});

export const conversations = pgTable("conversations", {
	id: varchar().primaryKey().notNull(),
	userId: varchar("user_id"),
	createdAt: timestamp("created_at", { mode: 'string' }),
}, (table) => [
	foreignKey({
			columns: [table.userId],
			foreignColumns: [users.id],
			name: "conversations_user_id_fkey"
		}),
]);

export const messages = pgTable("messages", {
	id: varchar().primaryKey().notNull(),
	conversationId: varchar("conversation_id"),
	role: varchar(),
	content: text(),
	createdAt: timestamp("created_at", { mode: 'string' }),
}, (table) => [
	foreignKey({
			columns: [table.conversationId],
			foreignColumns: [conversations.id],
			name: "messages_conversation_id_fkey"
		}),
]);

export const users = pgTable("users", {
	id: varchar().primaryKey().notNull(),
	email: varchar(),
	name: varchar(),
	profileData: json("profile_data"),
}, (table) => [
	uniqueIndex("ix_users_email").using("btree", table.email.asc().nullsLast().op("text_ops")),
]);

export const apiLogs = pgTable("api_logs", {
	id: varchar().primaryKey().notNull(),
	conversationId: varchar("conversation_id"),
	eventType: varchar("event_type"),
	payload: text(),
	createdAt: timestamp("created_at", { mode: 'string' }),
}, (table) => [
	foreignKey({
			columns: [table.conversationId],
			foreignColumns: [conversations.id],
			name: "api_logs_conversation_id_fkey"
		}),
]);
