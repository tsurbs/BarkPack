import { createFileRoute, useLoaderData } from "@tanstack/react-router";
import { Activity, Cpu, Server, Wrench } from "lucide-react";
import React, { useState } from "react";
import { getApiLogs } from "./-api";

export const Route = createFileRoute("/dashboard/logs")({
	component: LogsPage,
	loader: async () => {
		const logs = await getApiLogs();
		return { logs };
	},
});

function LogsPage() {
	const { logs } = useLoaderData({ from: "/dashboard/logs" });
	const [filter, setFilter] = useState<string>("all");
	const [expandedRow, setExpandedRow] = useState<string | null>(null);
	const [mounted, setMounted] = useState(false);

	React.useEffect(() => {
		setMounted(true);
	}, []);

	const filteredLogs = logs.filter((log) => {
		const et = log.eventType ?? "";
		if (filter === "all") return true;
		if (filter === "llm_request" && et === "openrouter_request") return true;
		if (filter === "llm_response" && et === "openrouter_response") return true;
		if (filter === "tool" && et.startsWith("tool_")) return true;
		return false;
	});

	const getEventIcon = (type: string | null) => {
		const t = type ?? "";
		if (t === "openrouter_request")
			return <Server size={14} className="text-blue-600" />;
		if (t === "openrouter_response")
			return <Cpu size={14} className="text-green-600" />;
		if (t.startsWith("tool_"))
			return <Wrench size={14} className="text-purple-600" />;
		return <Activity size={14} className="text-black-600" />;
	};

	const getEventColor = (type: string | null) => {
		const t = type ?? "";
		if (t === "openrouter_request")
			return "border-blue-200 bg-blue-50 text-blue-600 shadow-sm";
		if (t === "openrouter_response")
			return "border-green-200 bg-green-50 text-green-600 shadow-sm";
		if (t.startsWith("tool_"))
			return "border-purple-200 bg-purple-50 text-purple-600 shadow-sm";
		return "border-black-200 bg-black-50 text-black-600 shadow-sm";
	};

	const formatEventType = (type: string | null) => {
		return (type ?? "unknown")
			.split("_")
			.map((w) => w.charAt(0).toUpperCase() + w.slice(1))
			.join(" ");
	};

	return (
		<div className="space-y-6 animate-in fade-in duration-500">
			<div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4">
				<h2 className="text-2xl font-bold flex items-center gap-2">
					<Activity className="text-[var(--color-blue-600)]" />
					API Logs & Traces
				</h2>

				{/* Filter Toolbar */}
				<div className="inline-flex bg-black-50 rounded-lg p-1 border border-black-100">
					<button
						type="button"
						onClick={() => setFilter("all")}
						className={`px-3 py-1.5 text-xs font-semibold rounded-md transition-colors ${filter === "all" ? "bg-white text-black-900 shadow-sm border border-black-100" : "text-black-400 hover:text-black-900"}`}
					>
						All Logs
					</button>
					<button
						type="button"
						onClick={() => setFilter("llm_request")}
						className={`px-3 py-1.5 text-xs font-semibold rounded-md transition-colors ${filter === "llm_request" ? "bg-blue-50 border border-blue-200 text-blue-600 shadow-sm" : "text-black-400 hover:text-blue-600"}`}
					>
						LLM Requests
					</button>
					<button
						type="button"
						onClick={() => setFilter("llm_response")}
						className={`px-3 py-1.5 text-xs font-semibold rounded-md transition-colors ${filter === "llm_response" ? "bg-green-50 border border-green-200 text-green-600 shadow-sm" : "text-black-400 hover:text-green-600"}`}
					>
						LLM Responses
					</button>
					<button
						type="button"
						onClick={() => setFilter("tool")}
						className={`px-3 py-1.5 text-xs font-semibold rounded-md transition-colors ${filter === "tool" ? "bg-purple-50 border border-purple-200 text-purple-600 shadow-sm" : "text-black-400 hover:text-purple-600"}`}
					>
						Tools
					</button>
				</div>
			</div>

			<div className="scotty-card overflow-hidden">
				<div className="overflow-x-auto">
					<table className="w-full text-left border-collapse">
						<thead>
							<tr className="bg-black-50 border-b border-black-100 text-black-400 text-sm">
								<th className="py-3 px-4 font-medium">Timestamp</th>
								<th className="py-3 px-4 font-medium">Event Type</th>
								<th className="py-3 px-4 font-medium">Model / Tool</th>
								<th className="py-3 px-4 font-medium">Tokens</th>
								<th className="py-3 px-4 font-medium text-right">Action</th>
							</tr>
						</thead>
						<tbody className="divide-y divide-black-100/50 text-sm">
							{filteredLogs.map((log) => (
								<React.Fragment key={log.id}>
									<tr className="hover:bg-black-50 transition-colors">
										<td className="py-3 px-4 font-mono text-xs text-black-400 whitespace-nowrap">
											{mounted && log.createdAt
												? new Date(log.createdAt).toLocaleString(undefined, {
														month: "short",
														day: "2-digit",
														hour: "2-digit",
														minute: "2-digit",
														second: "2-digit",
													})
												: ""}
										</td>
										<td className="py-3 px-4">
											<span
												className={`inline-flex items-center gap-1.5 px-2.5 py-1 rounded-md border text-xs font-medium ${getEventColor(log.eventType)}`}
											>
												{getEventIcon(log.eventType)}
												{formatEventType(log.eventType)}
											</span>
										</td>
										<td className="py-3 px-4 font-mono text-xs text-black-500">
											{log.model !== "unknown"
												? log.model
												: log.payload?.tool
													? `${log.payload.tool}`
													: "-"}
										</td>
										<td className="py-3 px-4 font-mono text-blue-600 font-medium">
											{log.tokens ? log.tokens.toLocaleString() : "-"}
										</td>
										<td className="py-3 px-4 text-right">
											<button
												type="button"
												onClick={() =>
													setExpandedRow(expandedRow === log.id ? null : log.id)
												}
												className="text-xs bg-white hover:bg-black-50 border border-black-100 text-black-500 px-3 py-1.5 rounded transition-colors"
											>
												{expandedRow === log.id ? "Hide" : "View Payload"}
											</button>
										</td>
									</tr>

									{/* Expanded Payload Row */}
									{expandedRow === log.id && (
										<tr className="bg-black-50 border-l border-r border-black-100">
											<td colSpan={5} className="p-0">
												<div className="p-4 w-full">
													<pre className="text-xs text-black-900 font-mono leading-relaxed bg-white p-4 rounded-lg border border-black-100 shadow-inner max-h-[400px] overflow-y-auto whitespace-pre-wrap break-all">
														{JSON.stringify(log.payload, null, 2)}
													</pre>
												</div>
											</td>
										</tr>
									)}
								</React.Fragment>
							))}

							{filteredLogs.length === 0 && (
								<tr>
									<td
										colSpan={5}
										className="py-12 text-center text-black-400 italic"
									>
										No logs found matching this filter.
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
