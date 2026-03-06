import { createFileRoute, Link, Outlet } from "@tanstack/react-router";

export const Route = createFileRoute("/dashboard")({
  component: DashboardLayout,
});

function DashboardLayout() {
  return (
    <div className="min-h-screen bg-black-50 text-black-900 font-inter">
      <div className="max-w-[1200px] mx-auto px-10 py-10">
        <header className="mb-8">
          <h1 className="text-4xl font-bold mb-6">
            <span className="bg-(--brand-gradient) bg-clip-text">
              BarkPack
            </span>{" "}
            Observability
          </h1>

          <nav className="flex gap-2 border-b border-black-100 pb-[-1px]">
            <Link
              to="/dashboard"
              activeOptions={{ exact: true }}
              className="px-4 py-2 text-black-400 hover:text-black-900 scotty-tab border-b-2 border-transparent relative top-px"
              activeProps={{
                className: "text-blue-600 border-blue-600 font-bold",
              }}
            >
              Overview
            </Link>
            <Link
              to="/dashboard/conversations"
              className="px-4 py-2 text-black-400 hover:text-black-900 scotty-tab border-b-2 border-transparent relative top-px"
              activeProps={{
                className: "text-blue-600 border-blue-600 font-bold",
              }}
            >
              Conversations
            </Link>
            <Link
              to="/dashboard/logs"
              className="px-4 py-2 text-black-400 hover:text-black-900 scotty-tab border-b-2 border-transparent relative top-px"
              activeProps={{
                className: "text-blue-600 border-blue-600 font-bold",
              }}
            >
              API Logs
            </Link>
            <Link
              to="/dashboard/users"
              className="px-4 py-2 text-black-400 hover:text-black-900 scotty-tab border-b-2 border-transparent relative top-px"
              activeProps={{
                className: "text-blue-600 border-blue-600 font-bold",
              }}
            >
              Users
            </Link>
            <Link
              to="/dashboard/skills"
              className="px-4 py-2 text-black-400 hover:text-black-900 scotty-tab border-b-2 border-transparent relative top-px"
              activeProps={{
                className: "text-blue-600 border-blue-600 font-bold",
              }}
            >
              ✨ Agent Skills
            </Link>
            <Link
              to="/dashboard/tools"
              className="px-4 py-2 text-black-400 hover:text-black-900 scotty-tab border-b-2 border-transparent relative top-px"
              activeProps={{
                className: "text-blue-600 border-blue-600 font-bold",
              }}
            >
              🛠️ Tools
            </Link>
          </nav>
        </header>

        <main>
          <Outlet />
        </main>
      </div>
    </div>
  );
}
