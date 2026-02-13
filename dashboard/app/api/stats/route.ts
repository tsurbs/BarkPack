import { NextResponse } from "next/server";

const BARK_API_URL = process.env.BARK_API_URL || "http://localhost:8000";

export const dynamic = "force-dynamic";

export async function GET() {
  try {
    const res = await fetch(`${BARK_API_URL}/dashboard/stats`, {
      next: { revalidate: 0 },
      signal: AbortSignal.timeout(10000),
    });

    if (!res.ok) {
      throw new Error(`Backend returned ${res.status}`);
    }

    const data = await res.json();
    return NextResponse.json(data);
  } catch (error) {
    console.error("Stats proxy error:", error);
    return NextResponse.json(
      { error: "Failed to fetch stats from backend" },
      { status: 502 },
    );
  }
}
