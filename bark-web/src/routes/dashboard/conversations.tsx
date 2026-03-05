import { createFileRoute, useLoaderData } from "@tanstack/react-router";
import { Clock, MessageSquare, User as UserIcon, X } from "lucide-react";
import { useEffect, useState } from "react";
import { getConversationDetail, getConversations } from "./-api";

export const Route = createFileRoute("/dashboard/conversations")({
  component: ConversationsPage,
  loader: async () => {
    const convs = await getConversations();
    return { conversations: convs };
  },
});

function ConversationsPage() {
  const { conversations } = useLoaderData({ from: "/dashboard/conversations" });
  const [selectedConvId, setSelectedConvId] = useState<string | null>(null);
  const [chatMessages, setChatMessages] = useState<any[]>([]);
  const [loadingChat, setLoadingChat] = useState(false);
  const [mounted, setMounted] = useState(false);

  useEffect(() => {
    setMounted(true);
  }, []);

  useEffect(() => {
    if (selectedConvId) {
      setLoadingChat(true);
      (getConversationDetail as any)({ data: selectedConvId })
        .then((res: any) => {
          setChatMessages(res.messages || []);
        })
        .finally(() => {
          setLoadingChat(false);
        });
    } else {
      setChatMessages([]);
    }
  }, [selectedConvId]);

  return (
    <div className="space-y-6 animate-in fade-in duration-500">
      <div className="flex items-center justify-between">
        <h2 className="text-2xl font-bold flex items-center gap-2">
          <MessageSquare className="text-[var(--color-blue-600)]" />
          Conversations Explorer
        </h2>
        <span className="text-black-400 text-sm">
          Showing latest {conversations.length} records
        </span>
      </div>

      <div className="scotty-card overflow-hidden">
        <div className="overflow-x-auto">
          <table className="w-full text-left border-collapse">
            <thead>
              <tr className="bg-black-50 border-b border-black-100 text-black-400 text-sm">
                <th className="py-4 px-6 font-medium">Session ID / User</th>
                <th className="py-4 px-6 font-medium">Messages</th>
                <th className="py-4 px-6 font-medium">Started</th>
                <th className="py-4 px-6 font-medium hidden sm:table-cell">
                  Last Active
                </th>
              </tr>
            </thead>
            <tbody className="divide-y divide-black-100/50">
              {conversations.map((conv) => (
                <tr
                  key={conv.id}
                  className="hover:bg-black-50 transition-colors group"
                >
                  <td className="py-4 px-6">
                    <div className="flex items-start gap-3">
                      <div className="mt-1 p-2 bg-black-50 rounded-full text-blue-600 hidden sm:block">
                        <UserIcon size={16} />
                      </div>
                      <div>
                        {/* We will just link to the same page for now, or a detail page if we build it */}
                        <div className="font-bold text-black-900 group-hover:text-blue-600 transition-colors">
                          {conv.userName || "Anonymous User"}
                        </div>
                        {conv.userEmail && (
                          <div className="text-xs text-black-400">
                            {conv.userEmail}
                          </div>
                        )}
                        <div className="text-xs text-black-400 font-mono mt-1 bg-black-50 px-1.5 py-0.5 rounded inline-block">
                          {conv.id}
                        </div>
                      </div>
                    </div>
                  </td>
                  <td className="py-4 px-6">
                    <button
                      type="button"
                      onClick={() => setSelectedConvId(conv.id)}
                      className="inline-flex items-center justify-center bg-blue-50 text-blue-600 rounded-full px-3 py-1 font-bold border border-blue-200 hover:bg-blue-100 transition-colors cursor-pointer"
                    >
                      {conv.messageCount} msgs
                    </button>
                  </td>
                  <td className="py-4 px-6 text-black-400 text-sm">
                    {mounted
                      ? new Date(conv.createdAt).toLocaleString(undefined, {
                        month: "short",
                        day: "numeric",
                        hour: "2-digit",
                        minute: "2-digit",
                      })
                      : ""}
                  </td>
                  <td className="py-4 px-6 text-black-400 text-sm hidden sm:table-cell">
                    <div className="flex items-center gap-1.5">
                      <Clock
                        size={14}
                        className="text-black-400"
                      />
                      {mounted
                        ? conv.lastActive
                          ? new Date(conv.lastActive).toLocaleString(
                            undefined,
                            {
                              month: "short",
                              day: "numeric",
                              hour: "2-digit",
                              minute: "2-digit",
                            },
                          )
                          : "N/A"
                        : ""}
                    </div>
                  </td>
                </tr>
              ))}

              {conversations.length === 0 && (
                <tr>
                  <td
                    colSpan={4}
                    className="py-12 text-center text-black-400 italic"
                  >
                    No conversations found. Have you talked to Bark Bot yet?
                  </td>
                </tr>
              )}
            </tbody>
          </table>
        </div>
      </div>
      {/* Chat View Popup Modal */}
      {selectedConvId && (
        <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black-900/60 backdrop-blur-md animate-in fade-in duration-300">
          <div
            className="bg-white w-full max-w-2xl max-h-[85vh] rounded-[var(--radius-base)] shadow-2xl flex flex-col border border-black-100 scotty-card overflow-hidden"
            onClick={(e) => e.stopPropagation()}
          >
            <div className="p-5 border-b border-black-100 flex items-center justify-between bg-black-50">
              <div>
                <h3 className="font-bold text-black-900 flex items-center gap-2">
                  <MessageSquare size={20} className="text-blue-600" />
                  Conversation History
                </h3>
                <p className="text-xs text-black-400 font-mono mt-1">
                  {selectedConvId}
                </p>
              </div>
              <button
                type="button"
                onClick={() => setSelectedConvId(null)}
                className="text-black-400 hover:text-black-900 p-2 hover:bg-black-100 transition-all rounded-full"
              >
                <X size={24} />
              </button>
            </div>

            <div className="flex-1 overflow-y-auto p-6 space-y-6 bg-white custom-scrollbar-minimal">
              {loadingChat ? (
                <div className="h-40 flex items-center justify-center">
                  <div className="w-8 h-8 border-4 border-blue-600 border-t-transparent rounded-full animate-spin"></div>
                </div>
              ) : chatMessages.length === 0 ? (
                <div className="py-12 text-center text-black-400 italic">
                  No messages found for this session.
                </div>
              ) : (
                chatMessages.map((m) => (
                  <div
                    key={m.id}
                    className={`flex ${m.role === "user" ? "justify-end" : "justify-start"}`}
                  >
                    <div
                      className={`max-w-[85%] p-4 rounded-2xl shadow-sm ${m.role === "user"
                        ? "bg-blue-600 text-white rounded-tr-none"
                        : "bg-black-50 border border-black-100 text-black-900 rounded-tl-none"
                        }`}
                    >
                      <div className="flex items-center gap-2 mb-1.5 opacity-80 uppercase tracking-widest text-[10px] font-bold">
                        {m.role === "user" ? "You" : "Bark Bot"}
                      </div>
                      <p className="whitespace-pre-wrap text-sm leading-relaxed">
                        {m.content}
                      </p>
                      <div
                        className={`text-[9px] mt-2 font-medium ${m.role === "user" ? "text-blue-200" : "text-black-400"}`}
                      >
                        {mounted && m.createdAt
                          ? new Date(m.createdAt).toLocaleTimeString([], {
                            hour: "2-digit",
                            minute: "2-digit",
                          })
                          : ""}
                      </div>
                    </div>
                  </div>
                ))
              )}
            </div>

            <div className="p-4 bg-black-50 border-t border-black-100 flex justify-end">
              <button
                type="button"
                onClick={() => setSelectedConvId(null)}
                className="px-5 py-2 bg-black-900 text-white rounded-md font-bold hover:brightness-125 transition-all text-sm"
              >
                Close History
              </button>
            </div>
          </div>
          {/* Close on clicking backdrop */}
          <div
            className="absolute inset-0 -z-10"
            onClick={() => setSelectedConvId(null)}
          ></div>
        </div>
      )}
    </div>
  );
}
