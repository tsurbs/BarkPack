import { relations } from "drizzle-orm/relations";
import {
	apiLogs,
	contextSummaries,
	conversations,
	messages,
	users,
} from "./schema";

export const conversationsRelations = relations(
	conversations,
	({ one, many }) => ({
		user: one(users, {
			fields: [conversations.userId],
			references: [users.id],
		}),
		messages: many(messages),
		apiLogs: many(apiLogs),
		contextSummaries: many(contextSummaries),
	}),
);

export const usersRelations = relations(users, ({ many }) => ({
	conversations: many(conversations),
}));

export const messagesRelations = relations(messages, ({ one }) => ({
	conversation: one(conversations, {
		fields: [messages.conversationId],
		references: [conversations.id],
	}),
}));

export const apiLogsRelations = relations(apiLogs, ({ one }) => ({
	conversation: one(conversations, {
		fields: [apiLogs.conversationId],
		references: [conversations.id],
	}),
}));

export const contextSummariesRelations = relations(
	contextSummaries,
	({ one }) => ({
		conversation: one(conversations, {
			fields: [contextSummaries.conversationId],
			references: [conversations.id],
		}),
	}),
);
