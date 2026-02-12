"""Claude Code integration tool for Bark.

Provides `code_edit_agent` — sends coding tasks to the Claude Code server
running on EC2. The server runs `claude` CLI, edits files, commits, pushes,
and Railway auto-deploys.
"""

import logging
from typing import Any

import httpx

from bark.core.config import get_settings
from bark.core.tools import tool

logger = logging.getLogger(__name__)

CLIENT_TIMEOUT = 660  # Must exceed server's 600s task timeout


async def _call_claude_code_server(instruction: str, timeout: int = 600) -> dict[str, Any]:
    settings = get_settings()
    if not settings.claude_code_server_url:
        return {"error": "CLAUDE_CODE_SERVER_URL not configured"}

    url = f"{settings.claude_code_server_url.rstrip('/')}/task/sync"
    headers: dict[str, str] = {"Content-Type": "application/json"}
    if settings.claude_code_auth_token:
        headers["Authorization"] = f"Bearer {settings.claude_code_auth_token}"

    async with httpx.AsyncClient(timeout=CLIENT_TIMEOUT) as client:
        logger.info(f"[ClaudeCode] POST {url}")
        resp = await client.post(url, json={"instruction": instruction, "timeout": timeout}, headers=headers)
        resp.raise_for_status()
        return resp.json()


def _format_result(data: dict[str, Any]) -> str:
    status = data.get("status", "unknown")
    lines = []
    if status == "completed":
        lines.append("✅ *Code change completed*")
    elif status == "failed":
        lines.append("❌ *Code change failed*")
    else:
        lines.append(f"⏳ *Status: {status}*")

    diff = data.get("diff")
    if diff and diff != "(no file changes)":
        lines.append(f"\n*Changes:*\n```{diff[:800]}```")
    elif diff:
        lines.append("\n_No files were modified._")

    if data.get("pushed"):
        sha = data.get("commit_sha", "?")[:8]
        lines.append(f"\n🚀 *Pushed* — commit `{sha}`\n_Railway will auto-deploy._")

    result = data.get("result")
    if result:
        lines.append(f"\n*Output:*\n```{result[:1500]}```")
    error = data.get("error")
    if error:
        lines.append(f"\n*Error:*\n```{error[:800]}```")
    return "\n".join(lines)


@tool(
    name="code_edit_agent",
    description=(
        "Send a coding task to the Claude Code server to modify Bark's own codebase. "
        "Claude Code will edit files, run tests, commit, and push to GitHub — "
        "then Railway auto-deploys.\n\n"
        "Use when users ask to: add features/tools, fix bugs, refactor code, "
        "add integrations, update config, or any code change to Bark.\n\n"
        "⚠️ Modifies production code. Be specific in your instruction. "
        "Runs up to 10 minutes. Auto-pushes on success."
    ),
    parameters={
        "type": "object",
        "properties": {
            "task": {
                "type": "string",
                "description": "Detailed coding instruction. Be specific about files, behavior, testing.",
            },
            "context": {
                "type": "string",
                "description": "Conversation context — summarize what the user asked for.",
            },
        },
        "required": ["task"],
    },
)
async def code_edit_agent(task: str, context: str = "") -> str:
    parts = []
    if context:
        parts.append(f"## Context\n\n{context}")
    parts.append(f"## Task\n\n{task}")
    full = "\n\n---\n\n".join(parts)

    try:
        data = await _call_claude_code_server(full)
        if "error" in data and not data.get("status"):
            return f"❌ {data['error']}"
        return _format_result(data)
    except httpx.ConnectError:
        return "❌ *Claude Code server unreachable.* Is it running on EC2?"
    except httpx.TimeoutException:
        return "⏳ *Task timed out* (>10 min). Check server logs."
    except httpx.HTTPStatusError as e:
        if e.response.status_code == 401:
            return "❌ *Auth failed* — check CLAUDE_CODE_AUTH_TOKEN"
        return f"❌ *Server error:* HTTP {e.response.status_code}"
    except Exception as e:
        logger.exception("[ClaudeCode] error")
        return f"❌ *Error:* {e}"
