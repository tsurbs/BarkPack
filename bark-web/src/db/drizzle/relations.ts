import { relations } from "drizzle-orm/relations";
import { users, conversations, messages, apiLogs } from "./schema";

export const conversationsRelations = relations(conversations, ({one, many}) => ({
	user: one(users, {
		fields: [conversations.userId],
		references: [users.id]
	}),
	messages: many(messages),
	apiLogs: many(apiLogs),
}));

export const usersRelations = relations(users, ({many}) => ({
	conversations: many(conversations),
}));

export const messagesRelations = relations(messages, ({one}) => ({
	conversation: one(conversations, {
		fields: [messages.conversationId],
		references: [conversations.id]
	}),
}));

export const apiLogsRelations = relations(apiLogs, ({one}) => ({
	conversation: one(conversations, {
		fields: [apiLogs.conversationId],
		references: [conversations.id]
	}),
}));