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
		customSession(async ({ user, session }, ctx) => {
			const customSessionObject: Auth = { session, user };

			// Get the decoded access token from the user for the external provider
			try {
				const accessToken = await auth.api.getAccessToken({
					body: { providerId: "oidc" },
					headers: ctx.headers,
				});

				if (accessToken && accessToken.accessToken) {
					customSessionObject.session.accessToken = accessToken.accessToken;
				}
			} catch (e) {
				// Not authenticated with OIDC or accessToken failed to fetch
			}

			return customSessionObject;
		}),
	],
});
