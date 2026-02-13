import { NextResponse } from "next/server";

const BARK_API_URL = process.env.BARK_API_URL || "http://localhost:8000";

export const dynamic = "force-dynamic";

export async function GET() {
  try {
    const res = await fetch(`${BARK_API_URL}/dashboard/health`, {
      next: { revalidate: 0 },
      signal: AbortSignal.timeout(15000),
    });

    if (!res.ok) {
      throw new Error(`Backend returned ${res.status}`);
    }

    const data = await res.json();
    return NextResponse.json(data);
  } catch (error) {
    console.error("Health check proxy error:", error);
    // Return degraded status for all services when backend is unreachable
    return NextResponse.json({
      integrations: [
        { name: "Gmail", status: "down", latency: "—" },
        { name: "Google Drive", status: "down", latency: "—" },
        { name: "Notion", status: "down", latency: "—" },
        { name: "ScottyLabs Wiki", status: "down", latency: "—" },
        { name: "Google Calendar", status: "down", latency: "—" },
      ],
      error: "Backend unreachable",
    });
  }
}
