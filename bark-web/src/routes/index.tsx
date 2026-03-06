import { createFileRoute, Link } from "@tanstack/react-router";
import { Activity } from "lucide-react";

export const Route = createFileRoute("/")({ component: App });

function App() {
	return (
		<div className="min-h-[calc(100vh-72px)] bg-black-50 flex items-center justify-center">
			<section className="relative py-20 px-6 text-center w-full max-w-4xl mx-auto scotty-card shadow-lg bg-white">
				<div className="relative z-10">
					<div className="flex flex-col items-center justify-center gap-4 mb-6">
						<h1 className="text-5xl md:text-7xl font-bold text-black-900 tracking-tight">
							Bark
							<span className="bg-(--brand-gradient) bg-clip-text">Pack</span>
						</h1>
						<p className="text-xl md:text-2xl text-black-400 font-medium">
							AI Agent Management & Observability Platform
						</p>
					</div>

					<div className="mt-10 flex justify-center">
						<Link
							to="/dashboard"
							className="flex items-center gap-2 px-6 py-3 scotty-button bg-blue-600 hover:bg-blue-600/90 text-white font-bold text-lg"
						>
							<Activity className="w-5 h-5" />
							Go to Dashboard
						</Link>
					</div>
				</div>
			</section>
		</div>
	);
}
