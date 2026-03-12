import { createServerFn } from "@tanstack/react-start";
import { db } from "../db";
import { surfaceCredentials } from "../db/drizzle/schema";
import { eq, and } from "drizzle-orm";
import { getSession } from "better-auth/api";
import { v4 as uuidv4 } from "uuid";

export const getUserCredentials = createServerFn().handler(async () => {
	const session = await getSession();
	if (!session?.user) {
		throw new Error("Unauthorized");
	}

	const creds = await db
		.select({
			id: surfaceCredentials.id,
			surface: surfaceCredentials.surface,
			createdAt: surfaceCredentials.createdAt,
		})
		.from(surfaceCredentials)
		.where(eq(surfaceCredentials.userId, session.user.id));

	return creds;
});

export const addSurfaceCredential = createServerFn()
	.inputValidator((data: { surface: string; token: string }) => data)
	.handler(async ({ data }) => {
		const session = await getSession();
		if (!session?.user) {
			throw new Error("Unauthorized");
		}

		const existing = await db
			.select()
			.from(surfaceCredentials)
			.where(
				and(
					eq(surfaceCredentials.userId, session.user.id),
					eq(surfaceCredentials.surface, data.surface),
				),
			)
			.limit(1);

		if (existing.length > 0) {
			const updated = await db
				.update(surfaceCredentials)
				.set({ token: data.token, updatedAt: new Date().toISOString() })
				.where(eq(surfaceCredentials.id, existing[0].id))
				.returning();
			return updated[0];
		}

		const id = uuidv4();
		const inserted = await db
			.insert(surfaceCredentials)
			.values({
				id,
				userId: session.user.id,
				surface: data.surface,
				token: data.token,
				createdAt: new Date().toISOString(),
				updatedAt: new Date().toISOString(),
			})
			.returning();

		return inserted[0];
	});

export const removeSurfaceCredential = createServerFn()
	.inputValidator((data: { surface: string }) => data)
	.handler(async ({ data }) => {
		const session = await getSession();
		if (!session?.user) {
			throw new Error("Unauthorized");
		}

		await db
			.delete(surfaceCredentials)
			.where(
				and(
					eq(surfaceCredentials.userId, session.user.id),
					eq(surfaceCredentials.surface, data.surface),
				),
			);

		return { success: true };
	});
