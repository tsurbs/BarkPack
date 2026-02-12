"""Fullstack web development subagent tool for Bark.

Provides a `fullstack_agent` tool that spawns an autonomous subagent
capable of scaffolding, building, and deploying web applications to Vercel.
Uses the ScottyLabs Design System (SKILL.md) and has access to shell, file,
and deployment tools.
"""

import asyncio
import json
import logging
import os
import time
from pathlib import Path
from typing import Any

import httpx

from bark.core.config import get_settings
from bark.core.tools import tool
from bark.tools.volume_tools import VOLUME_PATH

logger = logging.getLogger(__name__)

# Max iterations the subagent conversation loop can run
MAX_ITERATIONS = 25
# Max seconds a single shell command can run
SHELL_TIMEOUT = 180
# Max characters of shell output to capture
MAX_OUTPUT_CHARS = 50_000

# ---------------------------------------------------------------------------
# Load SKILL.md (ScottyLabs Design System)
# ---------------------------------------------------------------------------

_SKILL_PATH = Path(__file__).resolve().parent / "skills" / "frontend.md"


def _load_skill() -> str:
    """Load the ScottyLabs Design System skill file."""
    try:
        return _SKILL_PATH.read_text(encoding="utf-8")
    except FileNotFoundError:
        logger.warning(f"SKILL.md not found at {_SKILL_PATH}")
        return "(Design system reference not available)"


FULLSTACK_SYSTEM_PROMPT = """You are a fullstack web development subagent running inside a sandboxed Docker container.
You have access to a workspace volume at {volume_path}.

Your job is to build and deploy web applications following the ScottyLabs Design System.

---

## ScottyLabs Design System Reference

{skill_content}

---

## Your Capabilities

You can build complete web applications:
- **Frontend:** React, Next.js, Vite — styled with Tailwind CSS and ScottyLabs design tokens
- **Backend/API:** Next.js API routes, serverless functions
- **Deployment:** Deploy to Vercel using the CLI

## Available Tools

- `shell_exec`: Execute a shell command. Returns stdout+stderr.
- `write_file`: Write content to a file on the volume.
- `read_file`: Read content from a file on the volume.

## Workflow

1. **Scaffold** the project (e.g., `npx create-next-app@latest ./project-name --ts --tailwind --app --use-npm --eslint`)
2. **Configure** Tailwind with ScottyLabs design tokens (extend `tailwind.config.ts`)
3. **Build** components and pages following the design system
4. **Test** locally with `npm run build` to verify no errors
5. **Deploy** to Vercel: `npx vercel --yes --token $VERCEL_TOKEN` (if a token is available)

## Guidelines

- Always work within the volume directory ({volume_path}).
- Follow the ScottyLabs Design System strictly — use Satoshi for headings, Inter for body text.
- Use even-number spacing (multiples of 2) for all paddings and margins.
- Use the ScottyLabs color tokens (scotty-red, scotty-dark, scotty-gray-*, etc.).
- Install packages with `npm install <package>` as needed.
- When done, provide a clear summary of what you built, the project structure, and the deployment URL (if deployed).
- If you encounter an error, try to fix it before giving up.
- Be efficient — don't repeat commands unnecessarily.
"""


# ---------------------------------------------------------------------------
# Inner tool implementations (shared with code_tools pattern)
# ---------------------------------------------------------------------------


def _safe_volume_path(subpath: str) -> Path:
    """Resolve a path safely under the volume root."""
    root = Path(VOLUME_PATH).resolve()
    target = (root / subpath).resolve()
    if not (target == root or str(target).startswith(str(root) + os.sep)):
        raise ValueError(f"Path escapes volume root: {subpath}")
    return target


async def _shell_exec(command: str, working_dir: str = "") -> str:
    """Execute a shell command and return output."""
    cwd = _safe_volume_path(working_dir) if working_dir else Path(VOLUME_PATH).resolve()

    # Inject VERCEL_TOKEN into the environment if available
    env = {**os.environ, "HOME": VOLUME_PATH}
    settings = get_settings()
    if settings.vercel_token:
        env["VERCEL_TOKEN"] = settings.vercel_token

    try:
        proc = await asyncio.create_subprocess_shell(
            command,
            cwd=str(cwd),
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.STDOUT,
            env=env,
        )
        try:
            stdout, _ = await asyncio.wait_for(proc.communicate(), timeout=SHELL_TIMEOUT)
        except asyncio.TimeoutError:
            proc.kill()
            return f"❌ Command timed out after {SHELL_TIMEOUT}s: {command}"

        output = stdout.decode("utf-8", errors="replace") if stdout else ""
        if len(output) > MAX_OUTPUT_CHARS:
            output = output[:MAX_OUTPUT_CHARS] + f"\n...(truncated at {MAX_OUTPUT_CHARS} chars)..."

        exit_code = proc.returncode
        if exit_code != 0:
            return f"[exit code {exit_code}]\n{output}"
        return output if output else "(no output)"

    except Exception as e:
        return f"❌ Error executing command: {e}"


def _write_file(path: str, content: str) -> str:
    """Write content to a file on the volume."""
    try:
        target = _safe_volume_path(path)
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(content, encoding="utf-8")
        return f"✅ Wrote {len(content)} chars to {target}"
    except Exception as e:
        return f"❌ Error writing file: {e}"


def _read_file(path: str, max_chars: int = 50000) -> str:
    """Read a file from the volume."""
    try:
        target = _safe_volume_path(path)
        if not target.exists():
            return f"❌ File not found: {path}"
        text = target.read_text(encoding="utf-8", errors="replace")
        if len(text) > max_chars:
            return text[:max_chars] + f"\n...(truncated at {max_chars} chars)..."
        return text
    except Exception as e:
        return f"❌ Error reading file: {e}"


# ---------------------------------------------------------------------------
# Inner tools available to the subagent
# ---------------------------------------------------------------------------

SUBAGENT_TOOLS = [
    {
        "type": "function",
        "function": {
            "name": "shell_exec",
            "description": (
                "Execute a shell command in the workspace. "
                "Returns stdout and stderr combined. "
                "Use for: npm commands, npx, git, vercel CLI, etc. "
                "Commands run with a 180-second timeout. "
                "VERCEL_TOKEN is available in the environment if configured."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "command": {
                        "type": "string",
                        "description": "The shell command to execute",
                    },
                    "working_dir": {
                        "type": "string",
                        "description": (
                            "Subdirectory within the volume to run in (optional, "
                            "defaults to volume root)"
                        ),
                    },
                },
                "required": ["command"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "write_file",
            "description": "Write content to a file in the workspace volume.",
            "parameters": {
                "type": "object",
                "properties": {
                    "path": {
                        "type": "string",
                        "description": "File path relative to the volume root",
                    },
                    "content": {
                        "type": "string",
                        "description": "File content to write",
                    },
                },
                "required": ["path", "content"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "read_file",
            "description": "Read a file from the workspace volume.",
            "parameters": {
                "type": "object",
                "properties": {
                    "path": {
                        "type": "string",
                        "description": "File path relative to the volume root",
                    },
                },
                "required": ["path"],
            },
        },
    },
]


async def _execute_subagent_tool(tool_name: str, args: dict[str, Any]) -> str:
    """Execute a subagent tool call."""
    if tool_name == "shell_exec":
        return await _shell_exec(
            command=args["command"],
            working_dir=args.get("working_dir", ""),
        )
    elif tool_name == "write_file":
        return _write_file(path=args["path"], content=args["content"])
    elif tool_name == "read_file":
        return _read_file(path=args["path"])
    else:
        return f"Unknown tool: {tool_name}"


# ---------------------------------------------------------------------------
# Autonomous subagent loop
# ---------------------------------------------------------------------------


async def _run_fullstack_subagent(task: str, model: str | None = None) -> str:
    """Run the fullstack subagent conversation loop.

    Returns the subagent's final text response.
    """
    settings = get_settings()
    model = model or settings.frontend_model

    # Ensure volume exists
    Path(VOLUME_PATH).mkdir(parents=True, exist_ok=True)

    # Build system prompt with SKILL.md content
    skill_content = _load_skill()
    system_prompt = FULLSTACK_SYSTEM_PROMPT.format(
        volume_path=VOLUME_PATH,
        skill_content=skill_content,
    )

    messages: list[dict[str, Any]] = [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": task},
    ]

    async with httpx.AsyncClient(
        base_url=settings.openrouter_base_url,
        headers={
            "Authorization": f"Bearer {settings.openrouter_api_key}",
            "Content-Type": "application/json",
        },
        timeout=300,
    ) as client:
        for iteration in range(MAX_ITERATIONS):
            logger.info(f"[FullstackAgent] Iteration {iteration + 1}/{MAX_ITERATIONS}")

            payload = {
                "model": model,
                "messages": messages,
                "tools": SUBAGENT_TOOLS,
                "tool_choice": "auto",
                "parallel_tool_calls": True,
            }

            start = time.time()
            resp = await client.post("/chat/completions", json=payload)
            duration = time.time() - start
            logger.info(f"[FullstackAgent] API request took {duration:.2f}s")
            resp.raise_for_status()
            data = resp.json()

            choice = data["choices"][0]
            message = choice["message"]

            # If done (no tool calls), return the final response
            if choice.get("finish_reason") == "stop" or not message.get("tool_calls"):
                return message.get("content", "(subagent returned no content)")

            # Add assistant message with tool calls
            messages.append(message)

            # Execute all tool calls in parallel
            async def _run_tool(tc: dict[str, Any]) -> dict[str, Any]:
                t_name = tc["function"]["name"]
                a_str = tc["function"].get("arguments", "{}") or "{}"
                t_args = json.loads(a_str)
                logger.info(f"[FullstackAgent] Tool: {t_name}({a_str[:200]})")
                result = await _execute_subagent_tool(t_name, t_args)
                logger.info(
                    f"[FullstackAgent] Result: {result[:200]}{'...' if len(result) > 200 else ''}"
                )
                return {
                    "role": "tool",
                    "content": result,
                    "tool_call_id": tc["id"],
                }

            tool_results = await asyncio.gather(
                *[_run_tool(tc) for tc in message["tool_calls"]]
            )
            messages.extend(tool_results)

        return "⚠️ Fullstack agent reached max iterations without completing. Last actions may have partial results."


# ---------------------------------------------------------------------------
# Public tool
# ---------------------------------------------------------------------------


@tool(
    name="fullstack_agent",
    description=(
        "Launch a fullstack web development subagent. The subagent can scaffold, "
        "build, and deploy complete web applications to Vercel. It follows the "
        "ScottyLabs Design System (Satoshi + Inter fonts, scotty-red brand colors, "
        "Tailwind CSS, even-number spacing).\n\n"
        "Use this for tasks like:\n"
        "- Building a new ScottyLabs website or landing page\n"
        "- Creating React/Next.js applications with proper branding\n"
        "- Setting up API routes and serverless functions\n"
        "- Deploying projects to Vercel\n"
        "- Prototyping UI components following the design system\n\n"
        "The subagent runs autonomously and returns a summary of what it built, "
        "including the deployment URL if deployed."
    ),
    parameters={
        "type": "object",
        "properties": {
            "task": {
                "type": "string",
                "description": (
                    "Detailed description of the web application to build. "
                    "Include what pages/features to create, the purpose of the app, "
                    "and whether to deploy to Vercel."
                ),
            },
        },
        "required": ["task"],
    },
)
async def fullstack_agent(task: str) -> str:
    """Launch a fullstack web development subagent."""
    try:
        result = await _run_fullstack_subagent(task)
        return f"**Fullstack Agent Result:**\n\n{result}"
    except httpx.HTTPStatusError as e:
        return f"❌ Fullstack agent API error: HTTP {e.response.status_code}"
    except Exception as e:
        logger.exception("Fullstack agent failed")
        return f"❌ Fullstack agent error: {e}"
