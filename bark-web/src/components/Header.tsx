import { Link } from "@tanstack/react-router";
import { Activity, Home, Menu, X } from "lucide-react";

import { useState } from "react";
import BetterAuthHeader from "../integrations/better-auth/header-user.tsx";

export default function Header() {
	const [isOpen, setIsOpen] = useState(false);

	return (
		<>
			<header className="p-4 flex items-center bg-white text-black-900 border-b border-black-100">
				<button
					type="button"
					onClick={() => setIsOpen(true)}
					className="p-2 hover:bg-black-50 rounded-lg transition-colors"
					aria-label="Open menu"
				>
					<Menu size={24} />
				</button>
				<h1 className="ml-4 text-xl font-bold">
					<Link to="/">
						<span className="bg-(--brand-gradient) bg-clip-text">BarkPack</span>
					</Link>
				</h1>
			</header>

			<aside
				className={`fixed top-0 left-0 h-full w-80 bg-white text-black-900 shadow-2xl z-50 transform transition-transform duration-300 ease-in-out flex flex-col border-r border-black-100 ${
					isOpen ? "translate-x-0" : "-translate-x-full"
				}`}
			>
				<div className="flex items-center justify-between p-4 border-b border-black-100">
					<h2 className="text-xl font-bold">Navigation</h2>
					<button
						type="button"
						onClick={() => setIsOpen(false)}
						className="p-2 hover:bg-black-50 rounded-lg transition-colors"
						aria-label="Close menu"
					>
						<X size={24} />
					</button>
				</div>

				<nav className="flex-1 p-4 overflow-y-auto">
					<Link
						to="/"
						onClick={() => setIsOpen(false)}
						className="flex items-center gap-3 p-3 rounded-lg hover:bg-black-50 transition-colors mb-2"
						activeProps={{
							className:
								"flex items-center gap-3 p-3 rounded-lg bg-blue-50 text-blue-600 font-bold transition-colors mb-2",
						}}
					>
						<Home size={20} />
						<span className="font-medium">Home</span>
					</Link>

					<Link
						to="/dashboard"
						onClick={() => setIsOpen(false)}
						className="flex items-center gap-3 p-3 rounded-lg hover:bg-black-50 transition-colors mb-2"
						activeProps={{
							className:
								"flex items-center gap-3 p-3 rounded-lg bg-blue-50 text-blue-600 font-bold transition-colors mb-2",
						}}
					>
						<Activity size={20} />
						<span className="font-medium">Dashboard</span>
					</Link>
				</nav>

				<div className="p-4 border-t border-black-100 bg-white flex flex-col gap-2">
					<BetterAuthHeader />
				</div>
			</aside>
		</>
	);
}
