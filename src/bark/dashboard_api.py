"""Dashboard API endpoints for the Bark observability dashboard.

Provides real-time data about memory statistics, service health,
and recent activity for the Next.js dashboard frontend.
"""

import logging
import os
import time
from pathlib import Path
from typing import Any

from fastapi import APIRouter

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/dashboard", tags=["dashboard"])

# Memory directory (same logic as memory_system.py)
MEMORY_DIR = Path("/app/data/memory") if Path("/app").exists() else Path("./data/memory")

COMMITTEES = [
    {"name": "Tech", "slug": "tech", "color": "#E03000"},
    {"name": "Labrador", "slug": "labrador", "color": "#2563EB"},
    {"name": "Design", "slug": "design", "color": "#7C3AED"},
    {"name": "Events", "slug": "events", "color": "#059669"},
    {"name": "Outreach", "slug": "outreach", "color": "#D97706"},
    {"name": "Finance", "slug": "finance", "color": "#0891B2"},
    {"name": "Foundry", "slug": "foundry", "color": "#DB2777"},
    {"name": "Admin", "slug": "admin", "color": "#6B7280"},
]


def _count_memory_files(folder: Path) -> int:
    """Recursively count .md files in a folder."""
    if not folder.exists():
        return 0
    return sum(
        1
        for f in folder.rglob("*.md")
        if not any(part.startswith(".") for part in f.parts)
        and f.name != "memory.json"
    )


def _relative_time(ts: float) -> str:
    """Convert a Unix timestamp to a human-readable relative string."""
    diff = time.time() - ts
    if diff < 60:
        return "just now"
    elif diff < 3600:
        mins = int(diff / 60)
        return f"{mins}m ago"
    elif diff < 86400:
        hours = int(diff / 3600)
        return f"{hours}h ago"
    else:
        days = int(diff / 86400)
        return f"{days}d ago"


def _get_last_modified(base: Path) -> float:
    """Get the most recent modification time among all .md files."""
    latest = 0.0
    if not base.exists():
        return latest
    for f in base.rglob("*.md"):
        try:
            mtime = f.stat().st_mtime
            if mtime > latest:
                latest = mtime
        except OSError:
            continue
    return latest


@router.get("/stats")
async def dashboard_stats() -> dict[str, Any]:
    """Return memory statistics and committee breakdowns.

    This reads the actual filesystem to count memory files per committee.
    """
    base = MEMORY_DIR.resolve()

    # Count files per committee
    committee_data = []
    total_memories = 0
    for c in COMMITTEES:
        folder = base / c["slug"]
        count = _count_memory_files(folder)
        total_memories += count
        committee_data.append({
            "name": c["name"],
            "slug": c["slug"],
            "memories": count,
            "color": c["color"],
        })

    # Count core.md as a memory too
    core_path = base / "core.md"
    if core_path.exists():
        total_memories += 1

    # Last activity time (most recent file modification)
    last_modified = _get_last_modified(base)
    last_activity = _relative_time(last_modified) if last_modified > 0 else "never"

    return {
        "stats": [
            {"label": "Total Memories", "value": str(total_memories), "icon": "🧠"},
            {"label": "Committees", "value": str(len(COMMITTEES)), "icon": "👥"},
            {"label": "Core Context", "value": "active" if core_path.exists() else "missing", "icon": "📋"},
            {"label": "Last Activity", "value": last_activity, "icon": "⏱️"},
        ],
        "committees": committee_data,
    }


@router.get("/health")
async def dashboard_health() -> dict[str, Any]:
    """Check health of Bark's integrated services.

    Makes lightweight API calls to each service to verify connectivity.
    Returns status and latency for each integration.
    """
    integrations = []

    # Check Gmail
    integrations.append(await _check_service(
        "Gmail",
        _check_gmail,
    ))

    # Check Google Drive
    integrations.append(await _check_service(
        "Google Drive",
        _check_drive,
    ))

    # Check Notion
    integrations.append(await _check_service(
        "Notion",
        _check_notion,
    ))

    # Check ScottyLabs Wiki
    integrations.append(await _check_service(
        "ScottyLabs Wiki",
        _check_wiki,
    ))

    # Check Google Calendar
    integrations.append(await _check_service(
        "Google Calendar",
        _check_calendar,
    ))

    return {"integrations": integrations}


async def _check_service(
    name: str,
    check_fn: Any,
) -> dict[str, Any]:
    """Run a health check function and capture status + latency."""
    import asyncio

    start = time.monotonic()
    try:
        await asyncio.wait_for(asyncio.to_thread(check_fn), timeout=10.0)
        elapsed_ms = int((time.monotonic() - start) * 1000)
        return {
            "name": name,
            "status": "operational",
            "latency": f"{elapsed_ms}ms",
        }
    except asyncio.TimeoutError:
        return {
            "name": name,
            "status": "degraded",
            "latency": ">10s",
        }
    except Exception as e:
        elapsed_ms = int((time.monotonic() - start) * 1000)
        logger.warning("Health check failed for %s: %s", name, e)
        return {
            "name": name,
            "status": "down",
            "latency": f"{elapsed_ms}ms",
        }


def _check_gmail() -> None:
    """Lightweight Gmail health check — list labels."""
    from bark.context.google_auth import get_google_auth

    auth = get_google_auth()
    service = auth.gmail
    service.users().labels().list(userId="me").execute()


def _check_drive() -> None:
    """Lightweight Drive health check — get about info."""
    from bark.context.google_auth import get_google_auth

    auth = get_google_auth()
    service = auth.drive
    service.about().get(fields="user").execute()


def _check_notion() -> None:
    """Lightweight Notion health check — search with empty query."""
    from bark.core.config import get_settings

    settings = get_settings()
    if not settings.notion_api_key:
        raise ValueError("NOTION_API_KEY not configured")

    import httpx

    resp = httpx.post(
        "https://api.notion.com/v1/search",
        headers={
            "Authorization": f"Bearer {settings.notion_api_key}",
            "Notion-Version": "2022-06-28",
            "Content-Type": "application/json",
        },
        json={"page_size": 1},
        timeout=8.0,
    )
    resp.raise_for_status()


def _check_wiki() -> None:
    """Lightweight Wiki health check — verify the repo URL is reachable."""
    from bark.core.config import get_settings

    settings = get_settings()
    import httpx

    # Convert git clone URL to an HTTP check
    url = settings.wiki_repo_url.replace(".git", "")
    resp = httpx.head(url, follow_redirects=True, timeout=8.0)
    resp.raise_for_status()


def _check_calendar() -> None:
    """Lightweight Calendar health check — list calendar list."""
    from bark.context.google_auth import get_google_auth

    auth = get_google_auth()
    service = auth.calendar
    service.calendarList().list(maxResults=1).execute()


@router.get("/activity")
async def dashboard_activity(limit: int = 50) -> dict[str, Any]:
    """Return recent activity log entries.

    Pulls from the in-memory ActivityLogger which records all tool calls.
    """
    from bark.core.activity_logger import get_activity_logger

    al = get_activity_logger()
    entries = al.get_recent(limit=limit)

    return {"activity": entries, "total": al.count()}
