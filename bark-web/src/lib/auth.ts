import { betterAuth, type Session, type User } from "better-auth";
import { drizzleAdapter } from "better-auth/adapters/drizzle";
import { customSession, genericOAuth } from "better-auth/plugins";
import { tanstackStartCookies } from "better-auth/tanstack-start";
import { db } from "../db";

interface Auth {
	session: Session & { accessToken?: string };
	user: User;
}

export const auth = betterAuth({
	baseURL: process.env.BETTER_AUTH_URL || "http://localhost:3000",
	database: drizzleAdapter(db, {
		provider: "pg",
	}),
	emailAndPassword: {
		enabled: true,
	},
	plugins: [
		tanstackStartCookies(),
		genericOAuth({
			config: [
				{
					providerId: "oidc",
					discoveryUrl: process.env.OIDC_ISSUER_URL
						? `${process.env.OIDC_ISSUER_URL.replace(/\/$/, "")}/.well-known/openid-configuration`
						: undefined,
					clientId: process.env.OIDC_CLIENT_ID || "",
					clientSecret: process.env.OIDC_CLIENT_SECRET || "",
					scopes: ["openid", "email", "profile"],
				},
			],
		}),
		customSession(async ({ user, session }) => {
			const customSessionObject: Auth = { session, user };

			try {
				// Fetch the user's accounts to get the OIDC ID Token directly from DB
				const oidcAccount = await db.query.account.findFirst({
					where: (account, { eq, and }) =>
						and(eq(account.userId, user.id), eq(account.providerId, "oidc")),
				});

				if (oidcAccount && oidcAccount.idToken) {
					customSessionObject.session.accessToken = oidcAccount.idToken;
				}
			} catch (e) {
				// Failed to fetch accounts or ID Token missing
			}

			return customSessionObject;
		}),
	],
});
