import { createFileRoute, Link, useLoaderData } from "@tanstack/react-router";
import {
  Activity,
  ArchiveRestore,
  ListTree,
  MessageSquare,
  Users,
} from "lucide-react";
import { useEffect, useState } from "react";
import {
  getActivityTimeline,
  getCompressionEvents,
  getConversations,
  getOverviewStats,
} from "./-api";

export const Route = createFileRoute("/dashboard/")({
  component: DashboardOverview,
  loader: async () => {
    const [stats, timeline, recentConversations, compressions] =
      await Promise.all([
        getOverviewStats(),
        getActivityTimeline(),
        getConversations(),
        getCompressionEvents(),
      ]);

    return {
      stats,
      timeline,
      recentConversations: recentConversations.slice(0, 10),
      compressions,
    };
  },
});

function DashboardOverview() {
  const { stats, timeline, recentConversations, compressions } = useLoaderData({
    from: "/dashboard/",
  });

  const [mounted, setMounted] = useState(false);
  useEffect(() => {
    setMounted(true);
  }, []);

  const maxTimelineVal = Math.max(
    ...timeline.map((t) => Math.max(t.messages, t.apiCalls)),
    1,
  );

  return (
    <div className="space-y-8 animate-in fade-in duration-500">
      {/* KPI Cards */}
      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-6">
        <div className="scotty-card p-6 flex items-center justify-between group">
          <div>
            <p className="text-black-400 text-sm font-medium mb-1 group-hover:text-blue-600 transition-colors">
              Total Users
            </p>
            <h3 className="text-3xl font-bold">
              {stats.totalUsers.toLocaleString()}
            </h3>
          </div>
          <div className="p-3 bg-black-50 rounded-[var(--radius-base)]">
            <Users size={24} className="text-[var(--color-blue-600)]" />
          </div>
        </div>

        <div className="scotty-card p-6 flex items-center justify-between group">
          <div>
            <p className="text-black-400 text-sm font-medium mb-1 group-hover:text-blue-600 transition-colors">
              Conversations
            </p>
            <h3 className="text-3xl font-bold">
              {stats.totalConversations.toLocaleString()}
            </h3>
          </div>
          <div className="p-3 bg-black-50 rounded-[var(--radius-base)]">
            <ListTree size={24} className="text-[var(--color-blue-600)]" />
          </div>
        </div>

        <div className="scotty-card p-6 flex items-center justify-between group">
          <div>
            <p className="text-black-400 text-sm font-medium mb-1 group-hover:text-blue-600 transition-colors">
              Messages
            </p>
            <h3 className="text-3xl font-bold">
              {stats.totalMessages.toLocaleString()}
            </h3>
          </div>
          <div className="p-3 bg-black-50 rounded-[var(--radius-base)]">
            <MessageSquare size={24} className="text-[var(--color-blue-600)]" />
          </div>
        </div>

        <div className="scotty-card p-6 flex items-center justify-between group">
          <div>
            <p className="text-black-400 text-sm font-medium mb-1 group-hover:text-blue-600 transition-colors">
              API Logs
            </p>
            <h3 className="text-3xl font-bold">
              {stats.totalApiCalls.toLocaleString()}
            </h3>
          </div>
          <div className="p-3 bg-black-50 rounded-[var(--radius-base)]">
            <Activity size={24} className="text-[var(--color-blue-600)]" />
          </div>
        </div>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-8">
        {/* Activity Timeline Chart (Pure CSS) */}
        <div className="lg:col-span-2 scotty-card p-6">
          <h2 className="text-xl font-bold mb-6 flex items-center gap-2">
            Activity Timeline (7 Days)
          </h2>
          <div className="h-64 flex items-end justify-between items-stretch gap-2 pt-6">
            {timeline.map((day) => {
              const msgHeight = Math.max(
                (day.messages / maxTimelineVal) * 100,
                2,
              );
              const apiHeight = Math.max(
                (day.apiCalls / maxTimelineVal) * 100,
                2,
              );

              // Format date nicely (e.g. 'Nov 12')
              const dateObj = new Date(`${day.date}T00:00:00`);
              const formattedDate = mounted
                ? dateObj.toLocaleDateString("en-US", {
                  month: "short",
                  day: "numeric",
                })
                : "";

              return (
                <div
                  key={day.date}
                  className="flex-1 flex flex-col justify-end items-center group relative cursor-pointer"
                >
                  {/* Tooltip */}
                  <div className="absolute -top-12 opacity-0 group-hover:opacity-100 transition-opacity bg-white border border-black-100 px-3 py-2 rounded-md text-xs whitespace-nowrap z-10 shadow-xl pointer-events-none text-black-900">
                    <p className="font-bold mb-1">{formattedDate}</p>
                    <p>
                      <span className="inline-block w-2 h-2 rounded-full bg-blue-600 mr-1"></span>{" "}
                      {day.messages} Messages
                    </p>
                    <p>
                      <span className="inline-block w-2 h-2 rounded-full bg-red-600 mr-1"></span>{" "}
                      {day.apiCalls} API Calls
                    </p>
                  </div>

                  <div className="w-full max-w-[40px] flex gap-1 items-end justify-center h-[200px] border-b border-black-100">
                    <div
                      className="w-1/2 bg-blue-600 rounded-t-sm transition-all duration-500 ease-out group-hover:brightness-125"
                      style={{ height: `${msgHeight}%` }}
                    ></div>
                    <div
                      className="w-1/2 bg-red-600 rounded-t-sm transition-all duration-500 ease-out group-hover:brightness-125 opacity-80"
                      style={{
                        height: `${apiHeight}%`,
                      }}
                    ></div>
                  </div>
                  <span className="text-xs text-black-400 mt-2 group-hover:text-black-900 transition-colors">
                    {formattedDate}
                  </span>
                </div>
              );
            })}
          </div>
        </div>

        {/* Mini Compression Stats */}
        <div className="scotty-card p-6 flex flex-col">
          <h2 className="text-xl font-bold mb-6 flex items-center gap-2">
            <ArchiveRestore size={20} className="text-purple-400" />
            Context Compressions
          </h2>

          <div className="flex-1 flex flex-col justify-center items-center text-center space-y-4">
            <h3 className="text-5xl font-black bg-clip-text bg-[var(--brand-gradient)]">
              {compressions.length}
            </h3>
            <p className="text-[var(--color-black-300)] text-sm">
              Total times history was compressed to save tokens
            </p>
          </div>

          {compressions.length > 0 && (
            <div className="mt-6 pt-6 border-t border-black-100">
              <p className="text-xs text-black-400 mb-2 uppercase tracking-wider">
                Latest Compression
              </p>
              <div className="text-sm">
                Saved{" "}
                <span className="text-blue-600 font-mono font-bold">
                  {compressions[0].messagesSummarized}
                </span>{" "}
                msgs
                <br />
                <span className="text-black-400">
                  {mounted
                    ? compressions[0].createdAt ? new Date(compressions[0].createdAt as string).toLocaleString() : ""
                    : ""}
                </span>
              </div>
            </div>
          )}
        </div>
      </div>

      {/* Recent Conversations */}
      <div className="scotty-card p-6">
        <h2 className="text-xl font-bold mb-6 flex items-center justify-between">
          Recent Conversations
          <Link
            to="/dashboard/conversations"
            className="text-sm text-blue-600 hover:text-blue-800 transition-colors flex items-center gap-1 font-bold"
          >
            View All &rarr;
          </Link>
        </h2>
        <div className="overflow-x-auto">
          <table className="w-full text-left border-collapse">
            <thead>
              <tr className="border-b border-black-100 text-black-400 text-sm">
                <th className="py-3 px-4 font-medium">User</th>
                <th className="py-3 px-4 font-medium">Messages</th>
                <th className="py-3 px-4 font-medium hidden sm:table-cell">
                  Created
                </th>
                <th className="py-3 px-4 font-medium">Last Active</th>
              </tr>
            </thead>
            <tbody>
              {recentConversations.map((conv) => (
                <tr
                  key={conv.id}
                  className="border-b border-black-100 hover:bg-black-50 transition-colors group"
                >
                  <td className="py-3 px-4">
                    <Link to="/dashboard/conversations" className="block">
                      <div className="font-bold group-hover:text-blue-600 transition-colors text-black-900">
                        {conv.userName || conv.userEmail || "Anonymous"}
                      </div>
                      <div className="text-xs text-black-400 font-mono mt-1">
                        {conv.id.substring(0, 8)}...
                      </div>
                    </Link>
                  </td>
                  <td className="py-3 px-4 whitespace-nowrap">
                    <span className="inline-flex items-center justify-center bg-blue-50 text-blue-600 rounded-full px-2.5 py-0.5 text-xs font-bold">
                      {conv.messageCount}
                    </span>
                  </td>
                  <td className="py-3 px-4 text-black-400 text-sm hidden sm:table-cell">
                    {mounted
                      ? new Date(conv.createdAt).toLocaleDateString()
                      : ""}
                  </td>
                  <td className="py-3 px-4 text-black-400 text-sm">
                    {mounted
                      ? conv.lastActive
                        ? new Date(conv.lastActive).toLocaleString()
                        : "N/A"
                      : ""}
                  </td>
                </tr>
              ))}
              {recentConversations.length === 0 && (
                <tr>
                  <td
                    colSpan={4}
                    className="py-8 text-center text-black-400 italic"
                  >
                    No conversations found.
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
