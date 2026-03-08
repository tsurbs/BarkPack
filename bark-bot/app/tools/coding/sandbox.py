"""Daytona sandbox lifecycle manager."""
import os
from typing import Optional, Dict, Any
from daytona_sdk import AsyncDaytona, DaytonaConfig

_client: Optional[AsyncDaytona] = None
_sandboxes: Dict[str, Any] = {}  # task_id → live sandbox object

SNAPSHOT = os.getenv("CODING_AGENT_SNAPSHOT", "daytonaio/sandbox:0.5.2")

def _get_client() -> AsyncDaytona:
    global _client
    if _client is None:
        _client = AsyncDaytona(DaytonaConfig(
            api_key=os.environ.get("DAYTONA_API_KEY", ""),
            api_url=os.getenv("DAYTONA_API_URL", "https://app.daytona.io/api"),
            target=os.getenv("DAYTONA_TARGET", "us"),
        ))
    return _client

async def get_sandbox(task_id: str) -> Optional[Any]:
    return _sandboxes.get(task_id)

async def require_sandbox(task_id: str) -> Any:
    """Return sandbox or raise if not found."""
    sb = _sandboxes.get(task_id)
    if not sb:
        # Try to resume if it exists on the server but not in memory
        client = _get_client()
        try:
            # We use task_id as the name or label to find it
            sandboxes_resp = await client.list()
            sandboxes = sandboxes_resp.items
            for s in sandboxes:
                if s.name == task_id or s.labels.get("task_id") == task_id:
                    _sandboxes[task_id] = s
                    return s
        except Exception:
            pass
            
        raise ValueError(
            f"No active sandbox for task_id={task_id!r}. "
            "Use sandbox_create first, or sandbox_resume if it already exists."
        )
    return sb

async def register_sandbox(task_id: str, sandbox: Any) -> None:
    _sandboxes[task_id] = sandbox

async def release_sandbox(task_id: str) -> None:
    sb = _sandboxes.pop(task_id, None)
    if sb:
        await sb.delete()

def get_client() -> AsyncDaytona:
    return _get_client()
