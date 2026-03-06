import { createFileRoute } from "@tanstack/react-router";
import { Plus, Save, Trash2 } from "lucide-react";
import { useEffect, useState } from "react";
import { authClient } from "../../lib/auth-client";

export const Route = createFileRoute("/dashboard/skills")({
	component: SkillsPage,
});

type Skill = {
	id: string;
	name: string;
	version: number;
	description: string;
};

const BACKEND_URL = import.meta.env.VITE_BACKEND_URL || "http://127.0.0.1:8000";

function SkillsPage() {
	const [skills, setSkills] = useState<Skill[]>([]);
	const [selectedSkillId, setSelectedSkillId] = useState<string | null>(null);
	const [yamlContent, setYamlContent] = useState<string>("");
	const [loading, setLoading] = useState(true);
	const [saving, setSaving] = useState(false);
	const [error, setError] = useState<string | null>(null);

	const { data: session } = authClient.useSession();

	useEffect(() => {
		if (session !== undefined) {
			fetchSkills();
		}
	}, [session]);

	const fetchSkills = async () => {
		try {
			setLoading(true);
			const headers: Record<string, string> = {};
			const userSession = session?.session as any;
			if (userSession?.accessToken) {
				headers["Authorization"] = `Bearer ${userSession.accessToken}`;
			}

			const res = await fetch(`${BACKEND_URL}/v1/agents`, { headers });
			if (!res.ok) throw new Error("Failed to fetch skills");
			const data = await res.json();
			setSkills(data);
			if (data.length > 0 && !selectedSkillId) {
				handleSelectSkill(data[0].id);
			}
		} catch (err: any) {
			setError(err.message);
		} finally {
			setLoading(false);
		}
	};

	const handleSelectSkill = async (id: string) => {
		try {
			setSelectedSkillId(id);
			setYamlContent("Loading...");
			const headers: Record<string, string> = {};
			const userSession = session?.session as any;
			if (userSession?.accessToken) {
				headers["Authorization"] = `Bearer ${userSession.accessToken}`;
			}

			const res = await fetch(`${BACKEND_URL}/v1/agents/${id}`, { headers });
			if (!res.ok) throw new Error("Failed to fetch skill details");
			const data = await res.json();
			setYamlContent(data.yaml_content);
		} catch (err: any) {
			setError(err.message);
			setYamlContent("");
		}
	};

	const handleSave = async () => {
		if (!selectedSkillId && !yamlContent.includes("id:")) {
			setError("New skills must have an 'id:' field in the YAML.");
			return;
		}

		try {
			setSaving(true);
			setError(null);
			const method = selectedSkillId ? "PUT" : "POST";
			const url = selectedSkillId
				? `${BACKEND_URL}/v1/agents/${selectedSkillId}`
				: `${BACKEND_URL}/v1/agents`;

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
				body: JSON.stringify({ yaml_content: yamlContent }),
			});

			if (!res.ok) {
				const errData = await res.json();
				throw new Error(errData.detail || "Failed to save skill");
			}

			await fetchSkills();
			if (!selectedSkillId) {
				// Find the new ID if it was a creation
				const idMatch = yamlContent.match(/id:\s*([^\n]+)/);
				if (idMatch) setSelectedSkillId(idMatch[1].trim());
			}
		} catch (err: any) {
			setError(err.message);
		} finally {
			setSaving(false);
		}
	};

	const handleDelete = async () => {
		if (!selectedSkillId) return;
		if (!confirm("Are you sure you want to delete this skill?")) return;

		try {
			setSaving(true);
			const headers: Record<string, string> = {};
			const userSession = session?.session as any;
			if (userSession?.accessToken) {
				headers["Authorization"] = `Bearer ${userSession.accessToken}`;
			}

			const res = await fetch(`${BACKEND_URL}/v1/agents/${selectedSkillId}`, {
				method: "DELETE",
				headers,
			});
			if (!res.ok) throw new Error("Failed to delete skill");
			setSelectedSkillId(null);
			setYamlContent("");
			await fetchSkills();
		} catch (err: any) {
			setError(err.message);
		} finally {
			setSaving(false);
		}
	};

	const handleCreateNew = () => {
		setSelectedSkillId(null);
		setYamlContent(
			`id: new_skill\nversion: 1\ntitle: New Skill\ndescription: A new dynamic skill.\nsystem_prompt: |\n  You are a helpful sub-agent.\nskill_prompt: |\n  Follow instructions carefully.\nactive_tools:\n  - search_tool`,
		);
	};

	return (
		<div className="space-y-6 animate-in fade-in duration-500">
			<div className="flex items-center justify-between">
				<h2 className="text-2xl font-bold flex items-center gap-2">
					✨ Agent Skills
				</h2>
				<button
					onClick={handleCreateNew}
					className="flex items-center gap-2 bg-blue-600 text-white px-4 py-2 rounded-md font-bold hover:bg-blue-700 transition"
				>
					<Plus size={16} /> New Skill
				</button>
			</div>

			{error && (
				<div className="bg-red-50 text-red-600 p-4 rounded-md border border-red-200 font-medium">
					{error}
				</div>
			)}

			<div className="grid grid-cols-1 md:grid-cols-3 gap-6 h-[70vh]">
				{/* Sidebar */}
				<div className="scotty-card overflow-hidden flex flex-col items-stretch">
					<div className="p-4 border-b border-black-100 bg-black-50 font-bold text-black-900">
						Available Skills
					</div>
					<div className="flex-1 overflow-y-auto p-2 space-y-1 bg-white">
						{loading && skills.length === 0 ? (
							<p className="text-black-400 p-4 text-center">
								Loading skills...
							</p>
						) : skills.length === 0 ? (
							<p className="text-black-400 p-4 text-center">No skills found.</p>
						) : (
							skills.map((skill) => (
								<button
									key={skill.id}
									onClick={() => handleSelectSkill(skill.id)}
									className={`w-full text-left p-3 rounded-md transition-colors ${selectedSkillId === skill.id ? "bg-blue-50 text-blue-700 font-bold" : "hover:bg-black-50 text-black-900"}`}
								>
									<div className="flex justify-between items-center">
										<span>{skill.name}</span>
										<span className="text-xs bg-white border border-black-200 px-1.5 py-0.5 rounded text-black-400">
											v{skill.version}
										</span>
									</div>
									<p className="text-xs text-black-400 mt-1 truncate">
										{skill.description}
									</p>
								</button>
							))
						)}
					</div>
				</div>

				{/* Editor */}
				<div className="md:col-span-2 scotty-card p-0 flex flex-col overflow-hidden">
					<div className="p-4 border-b border-black-100 bg-black-50 flex items-center justify-between">
						<h3 className="font-bold text-black-900">
							{selectedSkillId
								? `Editing: ${selectedSkillId}`
								: "Create New Skill"}
						</h3>
						<div className="flex gap-2">
							{selectedSkillId && (
								<button
									onClick={handleDelete}
									disabled={saving}
									className="flex items-center gap-1 text-red-600 px-3 py-1.5 rounded hover:bg-red-50 transition text-sm font-bold disabled:opacity-50"
								>
									<Trash2 size={14} /> Delete
								</button>
							)}
							<button
								onClick={handleSave}
								disabled={saving || !yamlContent}
								className="flex items-center gap-1 bg-black-900 text-white px-4 py-1.5 rounded hover:bg-black-700 transition text-sm font-bold disabled:opacity-50"
							>
								<Save size={14} /> {saving ? "Saving..." : "Save YAML"}
							</button>
						</div>
					</div>
					<div className="flex-1 bg-black-900 relative">
						<textarea
							value={yamlContent}
							onChange={(e) => setYamlContent(e.target.value)}
							className="absolute inset-0 w-full h-full p-6 bg-black-900 text-blue-400 font-mono text-sm resize-none focus:outline-none leading-relaxed"
							spellCheck={false}
							placeholder="Paste skill YAML here..."
						/>
					</div>
				</div>
			</div>
		</div>
	);
}
