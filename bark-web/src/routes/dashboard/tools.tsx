import { createFileRoute } from "@tanstack/react-router";
import { Code, Plus, Save, Server, Trash2, Wrench } from "lucide-react";
import { useEffect, useState } from "react";
import { authClient } from "../../lib/auth-client";

export const Route = createFileRoute("/dashboard/tools")({
	component: ToolsPage,
});

type Tool = {
	id: string;
	name: string;
	description: string;
	toolType: "native" | "python" | "mcp";
	content: string;
	createdAt: string;
	updatedAt: string;
};

const BACKEND_URL = import.meta.env.VITE_BACKEND_URL || "http://127.0.0.1:8000";

const DEFAULT_PYTHON_CODE = `class Args(BaseModel):
    query: str

async def run(self, args: Args, user, db) -> str:
    return f"You executed python with query: {args.query}"
`;

function ToolsPage() {
	const [tools, setTools] = useState<Tool[]>([]);
	const [selectedToolId, setSelectedToolId] = useState<string | null>(null);

	// Editor Form State
	const [name, setName] = useState("");
	const [description, setDescription] = useState("");
	const [toolType, setToolType] = useState<"python" | "mcp">("python");
	const [content, setContent] = useState("");

	const [loading, setLoading] = useState(true);
	const [saving, setSaving] = useState(false);
	const [error, setError] = useState<string | null>(null);

	const { data: session } = authClient.useSession();

	useEffect(() => {
		if (session !== undefined) {
			fetchTools();
		}
	}, [session]);

	const fetchTools = async () => {
		try {
			setLoading(true);
			const headers: Record<string, string> = {};
			const userSession = session?.session as any;
			if (userSession?.accessToken) {
				headers["Authorization"] = `Bearer ${userSession.accessToken}`;
			}

			const res = await fetch(`${BACKEND_URL}/v1/tools`, { headers });
			if (!res.ok) throw new Error("Failed to fetch tools");
			const data = await res.json();
			setTools(data);
			if (data.length > 0 && !selectedToolId) {
				handleSelectTool(data[0]);
			}
		} catch (err: any) {
			setError(err.message);
		} finally {
			setLoading(false);
		}
	};

	const handleSelectTool = (tool: Tool) => {
		setSelectedToolId(tool.id);
		setName(tool.name);
		setDescription(tool.description);
		if (tool.toolType !== "native") {
			setToolType(tool.toolType);
		} else {
			setToolType("python"); // Default fallback for UI if native selected (readonly anyway)
		}

		// For MCP, we might want to parse it for a nicer UI, but for now we'll just show the raw JSON or let the user edit the JSON
		// Or we provide a nice config builder if we want.
		setContent(tool.content || "");
		setError(null);
	};

	const handleSave = async () => {
		if (!name.trim()) {
			setError("Tool name is required.");
			return;
		}

		try {
			setSaving(true);
			setError(null);
			const method = selectedToolId ? "PUT" : "POST";
			const url = selectedToolId
				? `${BACKEND_URL}/v1/tools/${selectedToolId}`
				: `${BACKEND_URL}/v1/tools`;

			const headers: Record<string, string> = {
				"Content-Type": "application/json",
			};
			const userSession = session?.session as any;
			if (userSession?.accessToken) {
				headers["Authorization"] = `Bearer ${userSession.accessToken}`;
			}

			const res = await fetch(url, {
				method,
				headers,
				body: JSON.stringify({
					name,
					description,
					toolType,
					content,
				}),
			});

			if (!res.ok) {
				const errData = await res.json();
				throw new Error(errData.detail || "Failed to save tool");
			}

			const newTool = await res.json();
			await fetchTools();
			if (!selectedToolId) {
				setSelectedToolId(newTool.id);
			}
		} catch (err: any) {
			setError(err.message);
		} finally {
			setSaving(false);
		}
	};

	const handleDelete = async () => {
		if (!selectedToolId) return;
		if (!confirm("Are you sure you want to delete this tool?")) return;

		try {
			setSaving(true);
			const headers: Record<string, string> = {};
			const userSession = session?.session as any;
			if (userSession?.accessToken) {
				headers["Authorization"] = `Bearer ${userSession.accessToken}`;
			}

			const res = await fetch(`${BACKEND_URL}/v1/tools/${selectedToolId}`, {
				method: "DELETE",
				headers,
			});
			if (!res.ok) {
				const errData = await res.json();
				throw new Error(errData.detail || "Failed to delete tool");
			}
			setSelectedToolId(null);
			await fetchTools();
		} catch (err: any) {
			setError(err.message);
		} finally {
			setSaving(false);
		}
	};

	const handleCreateNew = () => {
		setSelectedToolId(null);
		setName("new_tool");
		setDescription("A newly created tool.");
		setToolType("python");
		setContent(DEFAULT_PYTHON_CODE);
		setError(null);
	};

	const selectedTool = tools.find((t) => t.id === selectedToolId);
	const isNative = selectedTool?.toolType === "native";

	return (
		<div className="space-y-6 animate-in fade-in duration-500">
			<div className="flex items-center justify-between">
				<h2 className="text-2xl font-bold flex items-center gap-2">
					🛠️ Tool Registry
				</h2>
				<button
					onClick={handleCreateNew}
					className="flex items-center gap-2 bg-blue-600 text-white px-4 py-2 rounded-md font-bold hover:bg-blue-700 transition"
				>
					<Plus size={16} /> New Tool
				</button>
			</div>

			{error && (
				<div className="bg-red-50 text-red-600 p-4 rounded-md border border-red-200 font-medium">
					{error}
				</div>
			)}

			<div className="grid grid-cols-1 md:grid-cols-3 gap-6 h-[75vh]">
				{/* Sidebar */}
				<div className="scotty-card overflow-hidden flex flex-col items-stretch">
					<div className="p-4 border-b border-black-100 bg-black-50 font-bold text-black-900">
						Registered Tools
					</div>
					<div className="flex-1 overflow-y-auto p-2 space-y-1 bg-white">
						{loading && tools.length === 0 ? (
							<p className="text-black-400 p-4 text-center">Loading tools...</p>
						) : tools.length === 0 ? (
							<p className="text-black-400 p-4 text-center">No tools found.</p>
						) : (
							tools.map((tool) => (
								<button
									key={tool.id}
									onClick={() => handleSelectTool(tool)}
									className={`w-full text-left p-3 rounded-md transition-colors ${selectedToolId === tool.id ? "bg-blue-50 text-blue-700 font-bold" : "hover:bg-black-50 text-black-900"}`}
								>
									<div className="flex justify-between items-center">
										<span className="font-medium flex items-center gap-1.5">
											{tool.toolType === "python" && (
												<Code size={14} className="text-green-600" />
											)}
											{tool.toolType === "mcp" && (
												<Server size={14} className="text-purple-600" />
											)}
											{tool.toolType === "native" && (
												<Wrench size={14} className="text-black-400" />
											)}
											{tool.name}
										</span>
									</div>
									<p className="text-xs text-black-400 mt-1 truncate">
										{tool.description}
									</p>
								</button>
							))
						)}
					</div>
				</div>

				{/* Editor Configuration */}
				<div className="md:col-span-2 flex flex-col gap-4 overflow-hidden">
					<div className="scotty-card p-6 border-b border-black-100 bg-white">
						<div className="flex justify-between items-start mb-4">
							<h3 className="font-bold text-lg text-black-900">
								{selectedToolId
									? isNative
										? "View Native Tool"
										: "Edit Tool"
									: "Create New Tool"}
							</h3>

							<div className="flex gap-2">
								{selectedToolId && !isNative && (
									<button
										onClick={handleDelete}
										disabled={saving}
										className="flex items-center gap-1 text-red-600 px-3 py-1.5 rounded hover:bg-red-50 transition text-sm font-bold disabled:opacity-50"
									>
										<Trash2 size={14} /> Delete
									</button>
								)}
								{!isNative && (
									<button
										onClick={handleSave}
										disabled={saving || !name}
										className="flex items-center gap-1 bg-black-900 text-white px-5 py-2 rounded-md hover:bg-black-700 transition text-sm font-bold disabled:opacity-50"
									>
										<Save size={14} /> {saving ? "Saving..." : "Save Tool"}
									</button>
								)}
							</div>
						</div>

						<div className="grid grid-cols-2 gap-4">
							<div>
								<label className="block text-sm font-bold text-black-900 mb-1">
									Tool Name
								</label>
								<input
									type="text"
									value={name}
									onChange={(e) => setName(e.target.value)}
									disabled={isNative}
									className="w-full border border-black-200 rounded-md px-3 py-2 text-sm focus:outline-none focus:border-blue-500 disabled:bg-black-50 disabled:text-black-400"
									placeholder="e.g. math_calculator"
								/>
							</div>
							<div>
								<label className="block text-sm font-bold text-black-900 mb-1">
									Type
								</label>
								<select
									value={isNative ? "native" : toolType}
									onChange={(e) => {
										setToolType(e.target.value as any);
										if (e.target.value === "mcp")
											setContent(
												'{\n  "command": "npx",\n  "args": ["-y", "@modelcontextprotocol/server-postgres", "postgresql://user:pass@localhost/db"],\n  "env": {}\n}',
											);
										else if (e.target.value === "python")
											setContent(DEFAULT_PYTHON_CODE);
									}}
									disabled={isNative}
									className="w-full border border-black-200 rounded-md px-3 py-2 text-sm focus:outline-none focus:border-blue-500 disabled:bg-black-50 disabled:text-black-400"
								>
									<option value="python">Python Script</option>
									<option value="mcp">MCP Server</option>
									{isNative && <option value="native">Native System</option>}
								</select>
							</div>
							<div className="col-span-2">
								<label className="block text-sm font-bold text-black-900 mb-1">
									Description
								</label>
								<input
									type="text"
									value={description}
									onChange={(e) => setDescription(e.target.value)}
									disabled={isNative}
									className="w-full border border-black-200 rounded-md px-3 py-2 text-sm focus:outline-none focus:border-blue-500 disabled:bg-black-50 disabled:text-black-400"
									placeholder="What does this tool do?"
								/>
							</div>
						</div>
					</div>

					{/* Code Editor Area */}
					<div className="flex-1 scotty-card p-0 flex flex-col overflow-hidden relative">
						<div className="p-3 border-b border-black-100 bg-black-50 flex items-center justify-between">
							<span className="font-bold text-sm text-black-900">
								{isNative
									? "Native Implementation Info"
									: toolType === "python"
										? "Python Source Code"
										: "MCP Configuration (JSON)"}
							</span>
						</div>
						{isNative ? (
							<div className="p-6 text-black-400 text-sm h-full flex items-center justify-center bg-black-50 text-center">
								This tool is native to the application codebase.
								<br />
								It cannot be edited via the web interface.
							</div>
						) : (
							<textarea
								value={content}
								onChange={(e) => setContent(e.target.value)}
								className="absolute inset-x-0 bottom-0 top-[45px] w-full p-4 bg-black-900 text-green-400 font-mono text-sm resize-none focus:outline-none leading-relaxed"
								spellCheck={false}
								placeholder={
									toolType === "python"
										? "Write python here..."
										: "Enter JSON configuration..."
								}
							/>
						)}
					</div>
				</div>
			</div>
		</div>
	);
}
