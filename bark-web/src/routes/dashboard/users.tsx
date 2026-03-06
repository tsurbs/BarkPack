import { createFileRoute, useLoaderData } from "@tanstack/react-router";
import { Hash, Mail, Users as UsersIcon } from "lucide-react";
import { useEffect, useState } from "react";
import { getUsers } from "./-api";

export const Route = createFileRoute("/dashboard/users")({
	component: UsersPage,
	loader: async () => {
		const users = await getUsers();
		return { users };
	},
});

function UsersPage() {
	const { users } = useLoaderData({ from: "/dashboard/users" });
	const [mounted, setMounted] = useState(false);

	useEffect(() => {
		setMounted(true);
	}, []);

	return (
		<div className="space-y-6 animate-in fade-in duration-500">
			<div className="flex items-center justify-between">
				<h2 className="text-2xl font-bold flex items-center gap-2">
					<UsersIcon className="text-[var(--color-blue-600)]" />
					User Directory
				</h2>
				<span className="text-black-400 text-sm">
					{users.length} active users
				</span>
			</div>

			<div className="scotty-card overflow-hidden">
				<div className="overflow-x-auto">
					<table className="w-full text-left border-collapse">
						<thead>
							<tr className="bg-black-50 border-b border-black-100 text-black-400 text-sm">
								<th className="py-4 px-6 font-medium">User Profile</th>
								<th className="py-4 px-6 font-medium">Conversations</th>
								<th className="py-4 px-6 font-medium hidden sm:table-cell">
									Latest Activity
								</th>
							</tr>
						</thead>
						<tbody className="divide-y divide-black-100/50">
							{users.map((user) => (
								<tr
									key={user.id}
									className="hover:bg-black-50 transition-colors group"
								>
									<td className="py-4 px-6">
										<div className="flex items-center gap-4">
											<div className="w-10 h-10 rounded-full bg-blue-50 flex items-center justify-center text-blue-600 font-bold border border-blue-200">
												{user.name ? user.name.charAt(0).toUpperCase() : "U"}
											</div>
											<div>
												<div className="font-bold text-black-900 group-hover:text-blue-600 transition-colors">
													{user.name || "Anonymous User"}
												</div>
												<div className="flex items-center gap-3 text-xs text-black-400 mt-1">
													{user.email && (
														<span className="flex items-center gap-1">
															<Mail size={12} /> {user.email}
														</span>
													)}
													<span className="flex items-center gap-1 font-mono bg-black-50 px-1 py-0.5 rounded text-black-400">
														<Hash size={12} /> {user.id.substring(0, 12)}...
													</span>
												</div>
											</div>
										</div>
									</td>
									<td className="py-4 px-6">
										<span className="inline-flex items-center justify-center bg-blue-50 text-blue-600 rounded-full px-3 py-1 font-bold border border-blue-200">
											{user.conversationCount}
										</span>
									</td>
									<td className="py-4 px-6 text-black-400 text-sm hidden sm:table-cell">
										{mounted
											? user.lastActive
												? new Date(user.lastActive).toLocaleString(undefined, {
														month: "short",
														day: "numeric",
														hour: "2-digit",
														minute: "2-digit",
													})
												: "N/A"
											: ""}
									</td>
								</tr>
							))}

							{users.length === 0 && (
								<tr>
									<td
										colSpan={3}
										className="py-12 text-center text-black-400 italic"
									>
										No users found in the database.
									</td>
								</tr>
							)}
						</tbody>
					</table>
				</div>
			</div>
		</div>
	);
}
