const STATS = [
  { label: "Total Memories", value: "15", icon: "🧠" },
  { label: "Wiki Articles", value: "42", icon: "📚" },
  { label: "Notion Pages", value: "128", icon: "📝" },
  { label: "Last Activity", value: "2m ago", icon: "⏱️" },
];

const COMMITTEES = [
  { name: "Tech", slug: "tech", memories: 5, color: "#E03000" },
  { name: "Labrador", slug: "labrador", memories: 3, color: "#2563EB" },
  { name: "Design", slug: "design", memories: 2, color: "#7C3AED" },
  { name: "Events", slug: "events", memories: 2, color: "#059669" },
  { name: "Outreach", slug: "outreach", memories: 1, color: "#D97706" },
  { name: "Finance", slug: "finance", memories: 1, color: "#0891B2" },
  { name: "Foundry", slug: "foundry", memories: 1, color: "#DB2777" },
  { name: "Admin", slug: "admin", memories: 0, color: "#6B7280" },
];

const INTEGRATIONS = [
  { name: "Gmail", status: "operational" as const, latency: "120ms" },
  { name: "Google Drive", status: "operational" as const, latency: "85ms" },
  { name: "Notion", status: "operational" as const, latency: "200ms" },
  { name: "ScottyLabs Wiki", status: "operational" as const, latency: "95ms" },
  { name: "Google Calendar", status: "operational" as const, latency: "110ms" },
];

const ACTIVITY_LOG = [
  {
    id: 1,
    action: "Memory saved",
    detail: "Tech committee meeting notes stored",
    committee: "tech",
    time: "2 minutes ago",
  },
  {
    id: 2,
    action: "Wiki queried",
    detail: 'Search: "TartanHacks 2025 schedule"',
    committee: "labrador",
    time: "8 minutes ago",
  },
  {
    id: 3,
    action: "Notion synced",
    detail: "Design assets page updated",
    committee: "design",
    time: "15 minutes ago",
  },
  {
    id: 4,
    action: "Memory saved",
    detail: "Outreach social media calendar Q1",
    committee: "outreach",
    time: "32 minutes ago",
  },
  {
    id: 5,
    action: "Calendar read",
    detail: "Fetched upcoming Events committee meetings",
    committee: "events",
    time: "1 hour ago",
  },
  {
    id: 6,
    action: "Drive accessed",
    detail: "Finance budget spreadsheet opened",
    committee: "finance",
    time: "1 hour ago",
  },
  {
    id: 7,
    action: "Memory recalled",
    detail: "Foundry mentor list retrieved",
    committee: "foundry",
    time: "2 hours ago",
  },
  {
    id: 8,
    action: "Wiki queried",
    detail: 'Search: "onboarding process"',
    committee: "admin",
    time: "3 hours ago",
  },
];

function StatusDot({ status }: { status: "operational" | "degraded" | "down" }) {
  const cls =
    status === "operational"
      ? "status-dot-green"
      : status === "degraded"
        ? "status-dot-yellow"
        : "status-dot-red";
  return <span className={cls} />;
}

function StatusLabel({ status }: { status: "operational" | "degraded" | "down" }) {
  const text =
    status === "operational"
      ? "Operational"
      : status === "degraded"
        ? "Degraded"
        : "Down";
  const color =
    status === "operational"
      ? "text-emerald-600"
      : status === "degraded"
        ? "text-amber-600"
        : "text-red-600";
  return <span className={`text-sm font-medium ${color}`}>{text}</span>;
}

function CommitteeBar({
  name,
  memories,
  color,
  maxMemories,
}: {
  name: string;
  memories: number;
  color: string;
  maxMemories: number;
}) {
  const pct = maxMemories > 0 ? (memories / maxMemories) * 100 : 0;
  return (
    <div className="flex items-center gap-4">
      <span className="w-24 text-sm font-medium text-text-secondary shrink-0">
        {name}
      </span>
      <div className="flex-1 h-7 bg-surface-tertiary rounded-lg overflow-hidden">
        <div
          className="h-full rounded-lg transition-all duration-500"
          style={{ width: `${pct}%`, backgroundColor: color }}
        />
      </div>
      <span className="w-8 text-sm font-semibold text-text-primary text-right tabular-nums">
        {memories}
      </span>
    </div>
  );
}

export default function Dashboard() {
  const maxMemories = Math.max(...COMMITTEES.map((c) => c.memories));
  const allOperational = INTEGRATIONS.every(
    (i) => i.status === "operational",
  );

  return (
    <div className="min-h-screen">
      {/* Header */}
      <header className="bg-white border-b border-border">
        <div className="max-w-7xl mx-auto px-6 py-5 flex items-center justify-between">
          <div className="flex items-center gap-3">
            <span className="text-2xl" role="img" aria-label="dog">
              🐕
            </span>
            <div>
              <h1 className="text-xl font-bold font-display text-text-primary tracking-tight">
                Bark Observability Dashboard
              </h1>
              <p className="text-sm text-text-tertiary">
                ScottyLabs Slack Bot &mdash; System Overview
              </p>
            </div>
          </div>
          <div className="flex items-center gap-2">
            {allOperational ? (
              <>
                <span className="status-dot-green" />
                <span className="text-sm font-medium text-emerald-600">
                  All Systems Operational
                </span>
              </>
            ) : (
              <>
                <span className="status-dot-yellow" />
                <span className="text-sm font-medium text-amber-600">
                  Degraded
                </span>
              </>
            )}
          </div>
        </div>
      </header>

      <main className="max-w-7xl mx-auto px-6 py-8 space-y-8">
        {/* Stat Cards */}
        <section>
          <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-5">
            {STATS.map((stat) => (
              <div key={stat.label} className="card p-6">
                <div className="flex items-start justify-between">
                  <div>
                    <p className="stat-label mb-1">{stat.label}</p>
                    <p className="stat-value text-text-primary">{stat.value}</p>
                  </div>
                  <span className="text-2xl" role="img" aria-label={stat.label}>
                    {stat.icon}
                  </span>
                </div>
              </div>
            ))}
          </div>
        </section>

        <div className="grid grid-cols-1 lg:grid-cols-3 gap-8">
          {/* Committee Breakdown */}
          <section className="lg:col-span-2">
            <div className="card p-6">
              <h2 className="text-lg font-semibold font-display text-text-primary mb-5">
                Memories by Committee
              </h2>
              <div className="space-y-3">
                {COMMITTEES.map((c) => (
                  <CommitteeBar
                    key={c.slug}
                    name={c.name}
                    memories={c.memories}
                    color={c.color}
                    maxMemories={maxMemories}
                  />
                ))}
              </div>
            </div>
          </section>

          {/* Integration Status */}
          <section>
            <div className="card p-6">
              <h2 className="text-lg font-semibold font-display text-text-primary mb-5">
                Integration Status
              </h2>
              <div className="space-y-4">
                {INTEGRATIONS.map((integration) => (
                  <div
                    key={integration.name}
                    className="flex items-center justify-between"
                  >
                    <div className="flex items-center gap-3">
                      <StatusDot status={integration.status} />
                      <span className="text-sm font-medium text-text-primary">
                        {integration.name}
                      </span>
                    </div>
                    <div className="flex items-center gap-3">
                      <span className="text-xs text-text-tertiary tabular-nums">
                        {integration.latency}
                      </span>
                      <StatusLabel status={integration.status} />
                    </div>
                  </div>
                ))}
              </div>
            </div>
          </section>
        </div>

        {/* Recent Activity */}
        <section>
          <div className="card p-6">
            <h2 className="text-lg font-semibold font-display text-text-primary mb-5">
              Recent Activity
            </h2>
            <div className="overflow-x-auto">
              <table className="w-full">
                <thead>
                  <tr className="border-b border-border">
                    <th className="text-left text-xs font-semibold text-text-tertiary uppercase tracking-wider pb-3 pr-4">
                      Action
                    </th>
                    <th className="text-left text-xs font-semibold text-text-tertiary uppercase tracking-wider pb-3 pr-4">
                      Detail
                    </th>
                    <th className="text-left text-xs font-semibold text-text-tertiary uppercase tracking-wider pb-3 pr-4">
                      Committee
                    </th>
                    <th className="text-right text-xs font-semibold text-text-tertiary uppercase tracking-wider pb-3">
                      Time
                    </th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-border">
                  {ACTIVITY_LOG.map((entry) => {
                    const committee = COMMITTEES.find(
                      (c) => c.slug === entry.committee,
                    );
                    return (
                      <tr key={entry.id} className="group">
                        <td className="py-3 pr-4">
                          <span className="inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-medium bg-primary-50 text-primary-700">
                            {entry.action}
                          </span>
                        </td>
                        <td className="py-3 pr-4 text-sm text-text-secondary">
                          {entry.detail}
                        </td>
                        <td className="py-3 pr-4">
                          <span
                            className="inline-flex items-center gap-1.5 text-sm font-medium"
                            style={{ color: committee?.color }}
                          >
                            <span
                              className="w-2 h-2 rounded-full"
                              style={{
                                backgroundColor: committee?.color,
                              }}
                            />
                            {committee?.name ?? entry.committee}
                          </span>
                        </td>
                        <td className="py-3 text-sm text-text-tertiary text-right whitespace-nowrap">
                          {entry.time}
                        </td>
                      </tr>
                    );
                  })}
                </tbody>
              </table>
            </div>
          </div>
        </section>

        {/* Footer */}
        <footer className="text-center py-4 text-sm text-text-tertiary">
          Bark &mdash; Built by{" "}
          <a
            href="https://scottylabs.org"
            target="_blank"
            rel="noopener noreferrer"
            className="text-primary hover:underline font-medium"
          >
            ScottyLabs
          </a>{" "}
          at Carnegie Mellon University
        </footer>
      </main>
    </div>
  );
}
