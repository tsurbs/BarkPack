import { createServerFn } from "@tanstack/react-start";
import { db } from "../db";
import {
	roles,
	userRoles,
	user as betterAuthUsers,
} from "../db/drizzle/schema";
import { eq, and } from "drizzle-orm";
import { getSession } from "better-auth/api";
import { v4 as uuidv4 } from "uuid";

// Note: `users` table matches the custom BarkBot `users` table, but BetterAuth uses `user` table.
// We'll join against the BetterAuth user table for admin displays since that's what has email.

export const getAllUsersWithRoles = createServerFn().handler(async () => {
	const session = await getSession();
	const sessionUser = (session as any)?.user;
	if (!sessionUser) throw new Error("Unauthorized");

	// Verify Admin (server-side guard)
	const adminEmailsRaw = process.env.ADMIN_EMAILS || "";
	const adminEmails = adminEmailsRaw
		.split(",")
		.map((e) => e.trim().toLowerCase())
		.filter((e) => e !== "");

	const isAdminByEmail =
		sessionUser.email && adminEmails.includes(sessionUser.email.toLowerCase());

	if (!isAdminByEmail) {
		const myRoles = await db
			.select({ roleName: roles.name })
			.from(userRoles)
			.innerJoin(roles, eq(userRoles.roleId, roles.id))
			.where(eq(userRoles.userId, sessionUser.id));

		if (!myRoles.some((r) => r.roleName === "admin" || r.roleName === "owner")) {
			throw new Error("Forbidden: Admin access required.");
		}
	}

	// Get all users
	const allUsers = await db.select().from(betterAuthUsers);

	// Get all role mappings
	const allMappings = await db
		.select({
			userId: userRoles.userId,
			roleName: roles.name,
		})
		.from(userRoles)
		.innerJoin(roles, eq(userRoles.roleId, roles.id));

	// Map roles to users
	return allUsers.map((u) => {
		const userRoleNames = allMappings
			.filter((m) => m.userId === u.id)
			.map((m) => m.roleName);
		return { ...u, roles: userRoleNames };
	});
});

export const assignRole = createServerFn()
	.inputValidator((data: { userId: string; roleName: string }) => data)
	.handler(async ({ data }) => {
		const session = await getSession();
		const sessionUser = (session as any)?.user;
		if (!sessionUser) throw new Error("Unauthorized");

		// Verify Admin
		const adminEmailsRaw = process.env.ADMIN_EMAILS || "";
		const adminEmails = adminEmailsRaw
			.split(",")
			.map((e) => e.trim().toLowerCase())
			.filter((e) => e !== "");

		const isAdminByEmail =
			sessionUser.email &&
			adminEmails.includes(sessionUser.email.toLowerCase());

		if (!isAdminByEmail) {
			const myRoles = await db
				.select({ roleName: roles.name })
				.from(userRoles)
				.innerJoin(roles, eq(userRoles.roleId, roles.id))
				.where(eq(userRoles.userId, sessionUser.id));

			if (
				!myRoles.some((r) => r.roleName === "admin" || r.roleName === "owner")
			) {
				throw new Error("Forbidden: Admin access required.");
			}
		}

		// Ensure role exists
		let role = await db
			.select()
			.from(roles)
			.where(eq(roles.name, data.roleName))
			.limit(1)
			.then((res) => res[0]);

		if (!role) {
			// Auto-create role if missing
			const inserted = await db
				.insert(roles)
				.values({
					id: uuidv4(),
					name: data.roleName,
					description: `Role ${data.roleName}`,
					createdAt: new Date().toISOString(),
				})
				.returning();
			role = inserted[0];
		}

		// Check if mapping exists
		const existing = await db
			.select()
			.from(userRoles)
			.where(
				and(eq(userRoles.userId, data.userId), eq(userRoles.roleId, role.id)),
			)
			.limit(1);

		if (existing.length === 0) {
			await db.insert(userRoles).values({
				id: uuidv4(),
				userId: data.userId,
				roleId: role.id,
				createdAt: new Date().toISOString(),
			});
		}

		return { success: true };
	});

export const revokeRole = createServerFn()
	.inputValidator((data: { userId: string; roleName: string }) => data)
	.handler(async ({ data }) => {
		const session = await getSession();
		const sessionUser = (session as any)?.user;
		if (!sessionUser) throw new Error("Unauthorized");

		// Verify Admin
		const adminEmailsRaw = process.env.ADMIN_EMAILS || "";
		const adminEmails = adminEmailsRaw
			.split(",")
			.map((e) => e.trim().toLowerCase())
			.filter((e) => e !== "");

		const isAdminByEmail =
			sessionUser.email &&
			adminEmails.includes(sessionUser.email.toLowerCase());

		if (!isAdminByEmail) {
			const myRoles = await db
				.select({ roleName: roles.name })
				.from(userRoles)
				.innerJoin(roles, eq(userRoles.roleId, roles.id))
				.where(eq(userRoles.userId, sessionUser.id));

			if (
				!myRoles.some((r) => r.roleName === "admin" || r.roleName === "owner")
			) {
				throw new Error("Forbidden: Admin access required.");
			}
		}

		const role = await db
			.select()
			.from(roles)
			.where(eq(roles.name, data.roleName))
			.limit(1)
			.then((res) => res[0]);

		if (role) {
			await db
				.delete(userRoles)
				.where(
					and(eq(userRoles.userId, data.userId), eq(userRoles.roleId, role.id)),
				);
		}

		return { success: true };
	});
