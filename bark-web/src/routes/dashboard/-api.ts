import { createServerFn } from "@tanstack/react-start";
import { count, desc, sql } from "drizzle-orm";
import { db } from "../../db";
import {
	apiLogs,
	contextSummaries,
	conversations,
	messages,
	users,
} from "../../db/drizzle/schema";

export const getOverviewStats = createServerFn({ method: "GET" }).handler(
	async () => {
		const [totalUsers] = await db.select({ value: count() }).from(users);
		const [totalConversations] = await db
			.select({ value: count() })
			.from(conversations);
		const [totalMessages] = await db.select({ value: count() }).from(messages);
		const [totalApiCalls] = await db.select({ value: count() }).from(apiLogs);

		return {
			totalUsers: totalUsers.value,
			totalConversations: totalConversations.value,
			totalMessages: totalMessages.value,
			totalApiCalls: totalApiCalls.value,
		};
	},
);

export const getActivityTimeline = createServerFn({ method: "GET" }).handler(
	async () => {
		// Aggregate messages and apiLogs by date mapping to the last 7 days
		// Raw SQL is easiest for date truncation
		const timelineResult = await db.execute(sql`
    WITH dates AS (
      SELECT generate_series(
        date_trunc('day', current_date - interval '6 days'),
        date_trunc('day', current_date),
        '1 day'::interval
      ) as "date"
    ),
    msg_counts AS (
      SELECT date_trunc('day', created_at::timestamp) as date, count(*) as count
      FROM messages
      WHERE created_at::timestamp >= current_date - interval '6 days'
      GROUP BY 1
    ),
    api_counts AS (
      SELECT date_trunc('day', created_at::timestamp) as date, count(*) as count
      FROM api_logs
      WHERE created_at::timestamp >= current_date - interval '6 days'
      GROUP BY 1
    )
    SELECT
      to_char(d.date, 'YYYY-MM-DD') as "date",
      COALESCE(m.count, 0) as "messages",
      COALESCE(a.count, 0) as "apiCalls"
    FROM dates d
    LEFT JOIN msg_counts m ON d.date = m.date
    LEFT JOIN api_counts a ON d.date = a.date
    ORDER BY d.date ASC
  `);

		return timelineResult.rows as {
			date: string;
			messages: number;
			apiCalls: number;
		}[];
	},
);

export const getConversations = createServerFn({ method: "GET" }).handler(
	async () => {
		const convs = await db.execute(sql`
    SELECT
      c.id, c.created_at as "createdAt",
      u.name as "userName", u.email as "userEmail",
      COUNT(m.id) as "messageCount",
      MAX(m.created_at) as "lastActive"
    FROM conversations c
    LEFT JOIN users u ON c.user_id = u.id
    LEFT JOIN messages m ON c.id = m.conversation_id
    GROUP BY c.id, c.created_at, u.name, u.email
    ORDER BY "lastActive" DESC NULLS LAST, c.created_at DESC
    LIMIT 100
  `);
		return convs.rows as any[];
	},
);

export const getConversationDetail = createServerFn({ method: "GET" }).handler(
	async (ctx: any) => {
		const conversationId = ctx.data as string;
		const msgs = await db
			.select()
			.from(messages)
			.where(sql`${messages.conversationId} = ${conversationId}`)
			.orderBy(messages.createdAt);

		return { messages: msgs };
	},
);

export const getApiLogs = createServerFn({ method: "GET" }).handler(
	async () => {
		const logs = await db
			.select()
			.from(apiLogs)
			.orderBy(desc(apiLogs.createdAt))
			.limit(200);

		return logs.map((log) => {
			let parsedPayload: any = {};
			try {
				if (log.payload) {
					parsedPayload = JSON.parse(log.payload);
				}
			} catch (_e) {}

			// Extract token usage
			const tokens = parsedPayload?.usage?.total_tokens
				? parsedPayload.usage.total_tokens
				: null;

			const model = parsedPayload?.model || "unknown";

			return {
				id: log.id,
				conversationId: log.conversationId,
				eventType: log.eventType,
				model,
				tokens,
				payload: parsedPayload,
				createdAt: log.createdAt,
			};
		});
	},
);

export const getUsers = createServerFn({ method: "GET" }).handler(async () => {
	const usersList = await db.execute(sql`
    SELECT
      u.id, u.name, u.email,
      COUNT(DISTINCT c.id) as "conversationCount",
      MAX(m.created_at) as "lastActive"
    FROM users u
    LEFT JOIN conversations c ON u.id = c.user_id
    LEFT JOIN messages m ON c.id = m.conversation_id
    GROUP BY u.id, u.name, u.email
    ORDER BY "lastActive" DESC NULLS LAST
    LIMIT 100
  `);
	return usersList.rows as any[];
});

export const getCompressionEvents = createServerFn({ method: "GET" }).handler(
	async () => {
		const events = await db
			.select()
			.from(contextSummaries)
			.orderBy(desc(contextSummaries.createdAt))
			.limit(50);
		return events;
	},
);
