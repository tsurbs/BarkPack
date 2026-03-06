import { LogOut, User } from "lucide-react";
import { authClient } from "../../lib/auth-client";

export default function BetterAuthHeader() {
	const { data: session, isPending } = authClient.useSession();

	if (isPending) {
		return <div className="text-xs text-black-400">Loading auth...</div>;
	}

	if (!session) {
		return (
			<button
				type="button"
				onClick={() => authClient.signIn.oauth2({ providerId: "oidc" })}
				className="flex items-center gap-2 p-2 text-sm font-medium text-black-600 hover:bg-black-50 rounded-lg transition-colors w-full"
			>
				<User size={16} />
				Sign In
			</button>
		);
	}

	return (
		<div className="flex items-center justify-between gap-2 p-2 bg-black-50 rounded-lg">
			<div className="flex items-center gap-2 overflow-hidden">
				{session.user.image ? (
					<img
						src={session.user.image}
						alt={session.user.name}
						className="w-8 h-8 rounded-full border border-black-100"
					/>
				) : (
					<div className="w-8 h-8 rounded-full bg-blue-100 text-blue-600 flex items-center justify-center font-bold">
						{session.user.name[0]}
					</div>
				)}
				<div className="flex flex-col overflow-hidden">
					<span className="text-sm font-bold truncate">
						{session.user.name}
					</span>
					<span className="text-xs text-black-400 truncate">
						{session.user.email}
					</span>
				</div>
			</div>
			<button
				type="button"
				onClick={() => authClient.signOut()}
				className="p-2 text-black-400 hover:text-red-500 hover:bg-red-50 rounded-lg transition-colors"
				title="Sign Out"
			>
				<LogOut size={16} />
			</button>
		</div>
	);
}
