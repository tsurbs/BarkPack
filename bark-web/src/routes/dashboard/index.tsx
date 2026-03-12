import { createFileRoute } from "@tanstack/react-router";
import { useServerFn } from "@tanstack/react-start";
import { useState, useEffect, useCallback } from "react";
import {
	getUserCredentials,
	addSurfaceCredential,
	removeSurfaceCredential,
} from "../../data/credentials";
import { getAllUsersWithRoles, assignRole, revokeRole } from "../../data/roles";

export const Route = createFileRoute("/dashboard/")({
	component: Dashboard,
});

function Dashboard() {
	const [credentials, setCredentials] = useState<
		Array<{ id: string; surface: string; createdAt: string }>
	>([]);
	const [users, setUsers] = useState<Array<any>>([]);
	const [error, setError] = useState<string | null>(null);

	// Form states
	const [newSurface, setNewSurface] = useState("");
	const [newToken, setNewToken] = useState("");

	// Server Fns
	const getCreds = useServerFn(getUserCredentials);
	const addCred = useServerFn(addSurfaceCredential);
	const rmCred = useServerFn(removeSurfaceCredential);

	const getUsers = useServerFn(getAllUsersWithRoles);
	const addRole = useServerFn(assignRole);
	const rmRole = useServerFn(revokeRole);

	const loadData = useCallback(async () => {
		try {
			setError(null);
			const credData = await getCreds();
			setCredentials(credData);

			// Attempt to load users (will fail if not admin)
			try {
				const userData = await getUsers();
				setUsers(userData);
			} catch (e) {
				// Not an admin, ignore
				console.log("Not an admin or error loading users:", e);
			}
		} catch (err: any) {
			setError(err.message || "Failed to load dashboard data");
		}
	}, [getCreds, getUsers]);

	useEffect(() => {
		loadData();
	}, [loadData]);

	const handleAddCredential = async (e: React.FormEvent) => {
		e.preventDefault();
		if (!newSurface || !newToken) return;
		try {
			await addCred({ data: { surface: newSurface, token: newToken } });
			setNewSurface("");
			setNewToken("");
			await loadData();
		} catch (err: any) {
			setError(err.message || "Failed to add credential");
		}
	};

	const handleDeleteCredential = async (surface: string) => {
		try {
			await rmCred({ data: { surface } });
			await loadData();
		} catch (err: any) {
			setError(err.message || "Failed to delete credential");
		}
	};

	const handleAssignRole = async (userId: string, roleName: string) => {
		if (!roleName) return;
		try {
			await addRole({ data: { userId, roleName } });
			await loadData();
		} catch (err: any) {
			setError(err.message || "Failed to assign role");
		}
	};

	const handleRevokeRole = async (userId: string, roleName: string) => {
		try {
			await rmRole({ data: { userId, roleName } });
			await loadData();
		} catch (err: any) {
			setError(err.message || "Failed to revoke role");
		}
	};

	return (
		<div className="p-6 max-w-4xl mx-auto space-y-8">
			<h1 className="text-3xl font-bold">Dashboard</h1>

			{error && (
				<div className="bg-red-50 text-red-600 p-4 rounded-md">{error}</div>
			)}

			{/* Surface Credentials Section */}
			<section className="bg-white p-6 rounded-lg shadow border border-gray-200">
				<h2 className="text-2xl font-semibold mb-4">My Surface Credentials</h2>

				<form onSubmit={handleAddCredential} className="flex gap-4 mb-6">
					<input
						type="text"
						placeholder="Surface (e.g. slack)"
						className="border p-2 rounded flex-1"
						value={newSurface}
						onChange={(e) => setNewSurface(e.target.value)}
					/>
					<input
						type="password"
						placeholder="Token"
						className="border p-2 rounded flex-1"
						value={newToken}
						onChange={(e) => setNewToken(e.target.value)}
					/>
					<button
						type="submit"
						className="bg-blue-600 text-white px-4 py-2 rounded hover:bg-blue-700"
					>
						Add
					</button>
				</form>

				<ul className="space-y-2">
					{credentials.map((cred) => (
						<li
							key={cred.id}
							className="flex justify-between items-center p-3 bg-gray-50 rounded border"
						>
							<div>
								<span className="font-medium capitalize">{cred.surface}</span>
								<span className="text-sm text-gray-500 ml-4 border-l pl-4 border-gray-300">
									Added: {new Date(cred.createdAt).toLocaleDateString()}
								</span>
							</div>
							<button
								type="button"
								onClick={() => handleDeleteCredential(cred.surface)}
								className="text-red-500 hover:text-red-700"
							>
								Delete
							</button>
						</li>
					))}
					{credentials.length === 0 && (
						<li className="text-gray-500 italic">No credentials added yet.</li>
					)}
				</ul>
			</section>

			{/* Admin Users Section */}
			{users.length > 0 && (
				<section className="bg-white p-6 rounded-lg shadow border border-gray-200">
					<h2 className="text-2xl font-semibold mb-4">
						User Management (Admin)
					</h2>
					<div className="overflow-x-auto">
						<table className="min-w-full text-left">
							<thead>
								<tr className="border-b">
									<th className="pb-3">Name</th>
									<th className="pb-3">Email</th>
									<th className="pb-3">Roles</th>
									<th className="pb-3">Actions</th>
								</tr>
							</thead>
							<tbody>
								{users.map((u) => (
									<tr
										key={u.id}
										className="border-b last:border-0 hover:bg-gray-50"
									>
										<td className="py-3">{u.name}</td>
										<td className="py-3 text-gray-600">{u.email}</td>
										<td className="py-3">
											<div className="flex gap-1 flex-wrap">
												{u.roles?.map((r: string) => (
													<span
														key={r}
														className="bg-gray-200 px-2 py-1 rounded text-xs flex items-center gap-1"
													>
														{r}
														<button
															type="button"
															onClick={() => handleRevokeRole(u.id, r)}
															className="text-red-500 ml-1 hover:text-red-700 font-bold"
														>
															×
														</button>
													</span>
												))}
											</div>
										</td>
										<td className="py-3">
											<select
												className="border rounded p-1 text-sm bg-white"
												onChange={(e) => {
													handleAssignRole(u.id, e.target.value);
													e.target.value = ""; // Reset
												}}
												defaultValue=""
											>
												<option value="" disabled>
													Add Role...
												</option>
												<option value="admin">Admin</option>
												<option value="user">User</option>
											</select>
										</td>
									</tr>
								))}
							</tbody>
						</table>
					</div>
				</section>
			)}
		</div>
	);
}
