# Coding Agent Task Plan: Add SWE Subagent to BarkPack
> For the autonomous coding agent executing this change
> v2 — Native BarkPack tools architecture (no OpenCode subprocess)

---

## Mission

Add a **software engineering subagent** (`coding_agent`) to the BarkPack codebase. The agent runs natively inside BarkPack's existing agent loop, using a set of new `sandbox_*` tools that talk directly to the Daytona SDK. OpenCode is used as a design reference — its tool designs, system prompt structure, and compaction schema — but is **not** installed as a runtime dependency. There is no subprocess, no nested agent loop, no black box.

When complete, the `bark_bot` orchestrator can delegate coding tasks to this skill via `load_skill("coding_agent")`. Every tool call the coding agent makes — every file read, bash command, git operation — appears as a first-class event in BarkPack's session DB, subject to `check_permissions`, and visible in the chat UI.

Before touching any files, log your plan using `create_agent_post`. After each major step, log progress. If you fail a step, log the failure and your recovery approach.

---

## Architecture Summary

```
bark_bot orchestrator
  └─► load_skill("coding_agent")
        └─► coding_agent loop  (standard BarkPack agent loop)
              ├─► sandbox_bash       → sandbox.process.executeCommand
              ├─► sandbox_read       → sandbox.fs.downloadFile
              ├─► sandbox_write      → sandbox.fs.uploadFile
              ├─► sandbox_edit       → download → patch → upload
              ├─► sandbox_glob       → sandbox.fs.findFiles
              ├─► sandbox_grep       → sandbox.process.executeCommand("rg ...")
              ├─► sandbox_list       → sandbox.fs.listFiles
              ├─► sandbox_git_status → sandbox.git.status
              ├─► sandbox_git_commit → sandbox.git.add + commit
              ├─► sandbox_git_push   → sandbox.git.push
              ├─► sandbox_test       → structured test runner + JSON capture
              ├─► sandbox_diff       → git diff → stored in coding_tasks
              ├─► sandbox_create     → daytona.create + git.clone
              ├─► sandbox_release    → sandbox.delete
              ├─► create_agent_post  (existing)
              └─► search_agent_posts (existing)
```

Every item in this chain is a real BarkPack tool call. All are visible in the session DB. All are subject to `check_permissions`. BarkPack's existing context compression handles the coding agent's session exactly as it does any other agent — no second compaction system.

---

## Pre-flight: Codebase Reconnaissance

Run all read operations before writing anything.

```
search_agent_posts("coding agent daytona sandbox")   # check for prior work
glob("bark-bot/app/agents/*.yaml")                   # existing skill definitions — study structure
glob("bark-bot/app/tools/*.py")                      # existing tools — study patterns
read("bark-bot/app/tools/base.py")                   # BaseTool interface — memorise signature
read("bark-bot/app/tools/registry.py")               # NATIVE_TOOLS map — understand format
read("bark-bot/app/agents/base.py")                  # AgentLoader — understand YAML loading + S3 sync
grep("check_permissions", "bark-bot/app/tools/")     # how permission gating works today
grep("args_schema", "bark-bot/app/tools/")           # Pydantic schema pattern
grep("context_compress", "bark-bot/app/")            # find the existing compression logic
read("bark-bot/pyproject.toml")                      # deps — confirm no daytonaio yet
```

Log findings to `create_agent_post`. Pay particular attention to: how `check_permissions` receives its `user` argument, what `BaseTool.run()` is expected to return on error, and whether any existing tool does multi-step Daytona-style API work (pattern to follow).

---

## Step 1 — Install Daytona SDK

```bash
cd bark-bot && uv add daytonaio
```

Verify:

```bash
cd bark-bot && uv run python -c "from daytona import Daytona, DaytonaConfig; print('daytona ok')"
```

If version conflicts appear, read `pyproject.toml`, resolve them, and log what changed.

---

## Step 2 — Create the DB Migration

**File**: `bark-bot/alembic/versions/{timestamp}_add_coding_tasks.py` *(new)*

Read the existing migration files first (`glob("bark-bot/alembic/versions/*.py")`) to match the exact pattern used by this project.

```python
"""Add coding_tasks table."""
from alembic import op
import sqlalchemy as sa
from pgvector.sqlalchemy import Vector

def upgrade():
    op.create_table(
        "coding_tasks",
        sa.Column("id", sa.UUID, primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("created_at", sa.TIMESTAMPTZ, nullable=False, server_default=sa.text("now()")),
        sa.Column("updated_at", sa.TIMESTAMPTZ, nullable=False, server_default=sa.text("now()")),

        # Identity
        sa.Column("task_id", sa.Text, unique=True, nullable=False),
        sa.Column("status", sa.Text, nullable=False, server_default="running"),
        # status values: running | awaiting_approval | complete | failed | abandoned

        # Source
        sa.Column("source_type", sa.Text),           # 'github_issue' | 'chat' | 'scheduled'
        sa.Column("github_issue_url", sa.Text),
        sa.Column("github_issue_number", sa.Integer),
        sa.Column("repo_url", sa.Text),
        sa.Column("branch", sa.Text),

        # Work product
        sa.Column("task_description", sa.Text),
        sa.Column("task_summary", sa.Text),           # populated by compaction-style summary
        sa.Column("commit_sha", sa.Text),
        sa.Column("pr_url", sa.Text),
        sa.Column("files_changed", sa.ARRAY(sa.Text)),
        sa.Column("diff_text", sa.Text),              # full git diff, stored before commit

        # Sandbox
        sa.Column("sandbox_id", sa.Text),
        sa.Column("sandbox_status", sa.Text, server_default="live"),  # live | deleted | expired
        sa.Column("preview_url", sa.Text),

        # Media artifacts: [{type, path, url, created_at}]
        sa.Column("media_artifacts", sa.JSON, server_default="[]"),

        # Test results
        sa.Column("tests_passed", sa.Integer),
        sa.Column("tests_failed", sa.Integer),
        sa.Column("test_output", sa.Text),

        # Token cost (from BarkPack's existing tracking)
        sa.Column("input_tokens", sa.Integer),
        sa.Column("output_tokens", sa.Integer),

        # Semantic deduplication
        sa.Column("task_embedding", Vector(1536)),
    )
    op.create_index(
        "ix_coding_tasks_embedding",
        "coding_tasks",
        ["task_embedding"],
        postgresql_using="ivfflat",
        postgresql_ops={"task_embedding": "vector_cosine_ops"},
    )
    op.create_index("ix_coding_tasks_repo_status", "coding_tasks", ["repo_url", "status"])
    op.create_index("ix_coding_tasks_task_id", "coding_tasks", ["task_id"])

def downgrade():
    op.drop_table("coding_tasks")
```

Run the migration:

```bash
cd bark-bot && uv run alembic upgrade head
```

Verify the table exists:

```bash
cd bark-bot && uv run python -c "
from app.db import get_session
import sqlalchemy as sa
with get_session() as s:
    result = s.execute(sa.text('SELECT count(*) FROM coding_tasks'))
    print('coding_tasks row count:', result.scalar())
"
```

---

## Step 3 — Sandbox Lifecycle Manager

**File**: `bark-bot/app/tools/coding/sandbox.py` *(new)*

Shared helper. Not a tool. Stores one sandbox per `task_id` so multiple tool calls within a single agent turn share the same container. Read `base.py` before writing to ensure `DaytonaConfig` usage matches project conventions.

```python
"""Daytona sandbox lifecycle manager. Not a tool — imported by sandbox_* tools."""
import os
from typing import Optional
from daytona import Daytona, DaytonaConfig

_client: Optional[Daytona] = None
_sandboxes: dict[str, object] = {}  # task_id → live sandbox object

SNAPSHOT = os.getenv("CODING_AGENT_SNAPSHOT", "swe-agent-base")


def _get_client() -> Daytona:
    global _client
    if _client is None:
        _client = Daytona(DaytonaConfig(
            api_key=os.environ["DAYTONA_API_KEY"],
            api_url=os.getenv("DAYTONA_API_URL", "https://app.daytona.io/api"),
            target=os.getenv("DAYTONA_TARGET", "us"),
        ))
    return _client


async def get_sandbox(task_id: str) -> Optional[object]:
    return _sandboxes.get(task_id)


async def require_sandbox(task_id: str) -> object:
    """Return sandbox or raise with a clear message if not found."""
    sb = _sandboxes.get(task_id)
    if not sb:
        raise ValueError(
            f"No active sandbox for task_id={task_id!r}. "
            "Use sandbox_create first, or check that the sandbox has not been released."
        )
    return sb


async def register_sandbox(task_id: str, sandbox: object) -> None:
    _sandboxes[task_id] = sandbox


async def release_sandbox(task_id: str) -> None:
    sb = _sandboxes.pop(task_id, None)
    if sb:
        await sb.delete()


def get_client() -> Daytona:
    return _get_client()
```

---

## Step 4 — Implement the Sandbox Tools

Create `bark-bot/app/tools/coding/` as a package with `__init__.py`. Each file below is one tool. Study `base.py` before starting — match the exact constructor, return type, and error convention.

**Critical pattern across all tools**: every tool that writes to the filesystem, runs bash, or changes git state must call `check_permissions(user)` before acting. Study existing tools for the exact call signature.

---

### Tool: `SandboxCreateTool`
**File**: `bark-bot/app/tools/coding/sandbox_create.py`

Creates a Daytona sandbox, clones the repo, registers the sandbox by task_id, and writes the initial `coding_tasks` row. This is the entry point — the coding agent calls this first, before any file or bash tools.

```python
from pydantic import BaseModel, Field
from app.tools.base import BaseTool
from .sandbox import get_client, register_sandbox, SNAPSHOT
from app.db import get_session
import uuid, sqlalchemy as sa

class SandboxCreateArgs(BaseModel):
    task_id: str = Field(
        default_factory=lambda: f"task-{uuid.uuid4().hex[:8]}",
        description="Unique task identifier. Auto-generated if omitted."
    )
    task_description: str = Field(..., description="Full description of the coding task")
    repo_url: str = Field(..., description="Git HTTPS URL of the repo to clone")
    branch: str = Field(default="main", description="Branch to clone")
    git_username: str = Field(default="")
    git_token: str = Field(default="", description="PAT for private repos")
    source_type: str = Field(default="chat", description="chat | github_issue | scheduled")
    github_issue_url: str = Field(default="")
    github_issue_number: int = Field(default=0)

class SandboxCreateTool(BaseTool):
    name = "sandbox_create"
    description = (
        "Create a Daytona sandbox and clone a git repo into it. "
        "Returns the task_id. Call this once at the start of every coding task. "
        "All subsequent sandbox_* tools use this task_id to find the sandbox."
    )
    args_schema = SandboxCreateArgs

    async def run(self, task_id: str, task_description: str, repo_url: str,
                  branch: str = "main", git_username: str = "", git_token: str = "",
                  source_type: str = "chat", github_issue_url: str = "",
                  github_issue_number: int = 0, user=None) -> str:
        self.check_permissions(user)

        client = get_client()
        sandbox = await client.create({"snapshot": SNAPSHOT})

        clone_kwargs = dict(url=repo_url, path="workspace/repo", branch=branch)
        if git_username and git_token:
            clone_kwargs.update(username=git_username, password=git_token)
        await sandbox.git.clone(**clone_kwargs)

        await register_sandbox(task_id, sandbox)

        # Write initial DB row
        with get_session() as session:
            session.execute(sa.text("""
                INSERT INTO coding_tasks
                  (task_id, status, task_description, repo_url, branch,
                   source_type, github_issue_url, github_issue_number, sandbox_id)
                VALUES
                  (:task_id, 'running', :desc, :repo_url, :branch,
                   :source_type, :issue_url, :issue_num, :sandbox_id)
            """), {
                "task_id": task_id, "desc": task_description,
                "repo_url": repo_url, "branch": branch,
                "source_type": source_type, "issue_url": github_issue_url,
                "issue_num": github_issue_number or None,
                "sandbox_id": getattr(sandbox, "id", None),
            })
            session.commit()

        return (
            f"Sandbox ready. task_id={task_id}\n"
            f"Repo cloned: {repo_url} @ {branch}\n"
            f"Workspace: /workspace/repo\n"
            f"Use task_id={task_id!r} for all subsequent sandbox_* calls."
        )
```

---

### Tool: `SandboxBashTool`
**File**: `bark-bot/app/tools/coding/sandbox_bash.py`

Runs a shell command inside the sandbox. This is the highest-risk tool — it gates on `check_permissions` and applies a deny list for destructive patterns before execution.

```python
import re
from pydantic import BaseModel, Field
from app.tools.base import BaseTool
from .sandbox import require_sandbox

# Commands that require explicit user approval before running.
# check_permissions handles the policy; this list provides the matching patterns.
SENSITIVE_PATTERNS = [
    r"\brm\s+-rf\b",
    r"\bgit\s+push\b",        # push is handled by sandbox_git_push with its own approval
    r"\bgit\s+reset\s+--hard\b",
    r"\bchmod\s+777\b",
    r"\bcurl\b.*\|\s*bash",   # curl-pipe-bash
    r"\bdrop\s+table\b",
    r"\btruncate\b",
]

class SandboxBashArgs(BaseModel):
    task_id: str = Field(..., description="Task ID identifying the target sandbox")
    command: str = Field(..., description="Shell command to run in /workspace/repo")
    workdir: str = Field(default="/workspace/repo", description="Working directory")

class SandboxBashTool(BaseTool):
    name = "sandbox_bash"
    description = (
        "Run a shell command inside the coding sandbox. "
        "Use for installing deps, running tests, checking build output, linting, etc. "
        "Do NOT use for git push — use sandbox_git_push instead."
    )
    args_schema = SandboxBashArgs

    async def run(self, task_id: str, command: str,
                  workdir: str = "/workspace/repo", user=None) -> str:
        self.check_permissions(user)

        for pattern in SENSITIVE_PATTERNS:
            if re.search(pattern, command, re.IGNORECASE):
                return (
                    f"BLOCKED: command matches sensitive pattern {pattern!r}.\n"
                    f"Command: {command}\n"
                    f"If this is intentional, use the appropriate dedicated tool "
                    f"(e.g. sandbox_git_push) or request explicit approval."
                )

        sandbox = await require_sandbox(task_id)
        full_command = f"cd {workdir} && {command}"
        result = await sandbox.process.executeCommand(full_command)

        output = result.result or ""
        exit_code = result.exitCode

        return (
            f"Exit code: {exit_code}\n"
            f"{'--- stdout ---' if output else '(no output)'}\n"
            f"{output}"
        ).strip()
```

---

### Tool: `SandboxReadTool`
**File**: `bark-bot/app/tools/coding/sandbox_read.py`

```python
from pydantic import BaseModel, Field
from app.tools.base import BaseTool
from .sandbox import require_sandbox

class SandboxReadArgs(BaseModel):
    task_id: str
    path: str = Field(..., description="Absolute path inside the sandbox, e.g. /workspace/repo/src/app.py")

class SandboxReadTool(BaseTool):
    name = "sandbox_read"
    description = "Read a file from the coding sandbox. Returns the file content as text."
    args_schema = SandboxReadArgs

    async def run(self, task_id: str, path: str, user=None) -> str:
        self.check_permissions(user)
        sandbox = await require_sandbox(task_id)
        content = await sandbox.fs.downloadFile(path)
        return content.decode("utf-8", errors="replace")
```

---

### Tool: `SandboxWriteTool`
**File**: `bark-bot/app/tools/coding/sandbox_write.py`

```python
from pydantic import BaseModel, Field
from app.tools.base import BaseTool
from .sandbox import require_sandbox

class SandboxWriteArgs(BaseModel):
    task_id: str
    path: str = Field(..., description="Absolute path. Parent directories are created if needed.")
    content: str = Field(..., description="Full file content to write")

class SandboxWriteTool(BaseTool):
    name = "sandbox_write"
    description = (
        "Write (create or overwrite) a file in the coding sandbox. "
        "Prefer sandbox_edit for targeted changes to existing files."
    )
    args_schema = SandboxWriteArgs

    async def run(self, task_id: str, path: str, content: str, user=None) -> str:
        self.check_permissions(user)
        sandbox = await require_sandbox(task_id)
        await sandbox.fs.uploadFile(content.encode("utf-8"), path)
        return f"Written: {path} ({len(content)} chars)"
```

---

### Tool: `SandboxEditTool`
**File**: `bark-bot/app/tools/coding/sandbox_edit.py`

Targeted string replacement. Fails explicitly if the old string is not found or appears more than once, preventing silent misapplications.

```python
from pydantic import BaseModel, Field
from app.tools.base import BaseTool
from .sandbox import require_sandbox

class SandboxEditArgs(BaseModel):
    task_id: str
    path: str = Field(..., description="Absolute path to the file to edit")
    old_str: str = Field(..., description="Exact string to replace. Must appear exactly once.")
    new_str: str = Field(..., description="Replacement string")

class SandboxEditTool(BaseTool):
    name = "sandbox_edit"
    description = (
        "Replace a unique string in a sandbox file. "
        "old_str must appear exactly once — use sandbox_read first to confirm the exact text."
    )
    args_schema = SandboxEditArgs

    async def run(self, task_id: str, path: str,
                  old_str: str, new_str: str, user=None) -> str:
        self.check_permissions(user)
        sandbox = await require_sandbox(task_id)

        raw = await sandbox.fs.downloadFile(path)
        content = raw.decode("utf-8", errors="replace")

        count = content.count(old_str)
        if count == 0:
            return f"EDIT FAILED: old_str not found in {path}.\nUse sandbox_read to inspect the file first."
        if count > 1:
            return (
                f"EDIT FAILED: old_str appears {count} times in {path}. "
                f"Make old_str more specific so it matches exactly once."
            )

        new_content = content.replace(old_str, new_str, 1)
        await sandbox.fs.uploadFile(new_content.encode("utf-8"), path)
        return f"Edited: {path}"
```

---

### Tool: `SandboxGlobTool`
**File**: `bark-bot/app/tools/coding/sandbox_glob.py`

```python
from pydantic import BaseModel, Field
from app.tools.base import BaseTool
from .sandbox import require_sandbox

class SandboxGlobArgs(BaseModel):
    task_id: str
    pattern: str = Field(..., description="Glob pattern, e.g. **/*.py or src/**/*.ts")
    root: str = Field(default="/workspace/repo")

class SandboxGlobTool(BaseTool):
    name = "sandbox_glob"
    description = "Find files by glob pattern in the sandbox. Returns a newline-separated list of matching paths."
    args_schema = SandboxGlobArgs

    async def run(self, task_id: str, pattern: str,
                  root: str = "/workspace/repo", user=None) -> str:
        self.check_permissions(user)
        sandbox = await require_sandbox(task_id)
        # Use find via bash — more reliable than SDK glob for nested patterns
        result = await sandbox.process.executeCommand(
            f'find {root} -type f -name "{pattern.split("/")[-1]}" '
            f'| grep -E "{pattern.replace("**", ".*").replace("*", "[^/]*")}" '
            f'| sort | head -100'
        )
        if not result.result.strip():
            return f"No files matched pattern {pattern!r} under {root}"
        return result.result.strip()
```

---

### Tool: `SandboxGrepTool`
**File**: `bark-bot/app/tools/coding/sandbox_grep.py`

```python
from pydantic import BaseModel, Field
from app.tools.base import BaseTool
from .sandbox import require_sandbox

class SandboxGrepArgs(BaseModel):
    task_id: str
    pattern: str = Field(..., description="Regex pattern to search for")
    path: str = Field(default="/workspace/repo", description="File or directory to search")
    case_sensitive: bool = Field(default=True)

class SandboxGrepTool(BaseTool):
    name = "sandbox_grep"
    description = "Search file contents in the sandbox using ripgrep. Returns matching lines with file:line context."
    args_schema = SandboxGrepArgs

    async def run(self, task_id: str, pattern: str,
                  path: str = "/workspace/repo",
                  case_sensitive: bool = True, user=None) -> str:
        self.check_permissions(user)
        sandbox = await require_sandbox(task_id)
        flags = "" if case_sensitive else "-i"
        result = await sandbox.process.executeCommand(
            f'rg {flags} --line-number --max-count 50 {pattern!r} {path}'
        )
        return result.result.strip() or f"No matches for {pattern!r} in {path}"
```

---

### Tool: `SandboxListTool`
**File**: `bark-bot/app/tools/coding/sandbox_list.py`

```python
from pydantic import BaseModel, Field
from app.tools.base import BaseTool
from .sandbox import require_sandbox

class SandboxListArgs(BaseModel):
    task_id: str
    path: str = Field(default="/workspace/repo")

class SandboxListTool(BaseTool):
    name = "sandbox_list"
    description = "List files and directories in a sandbox path."
    args_schema = SandboxListArgs

    async def run(self, task_id: str, path: str = "/workspace/repo", user=None) -> str:
        self.check_permissions(user)
        sandbox = await require_sandbox(task_id)
        files = await sandbox.fs.listFiles(path)
        lines = []
        for f in files:
            marker = "/" if f.isDir else ""
            lines.append(f"{'d' if f.isDir else '-'}  {f.name}{marker}  ({f.size} bytes)")
        return "\n".join(lines) if lines else f"(empty directory: {path})"
```

---

### Tool: `SandboxTestTool`
**File**: `bark-bot/app/tools/coding/sandbox_test.py`

Runs the project's test suite and returns structured results. Writes pass/fail counts to `coding_tasks`. The test command is read from `github_repos` config if available, falling back to detection heuristics.

```python
import json, re
from pydantic import BaseModel, Field
from app.tools.base import BaseTool
from .sandbox import require_sandbox
from app.db import get_session
import sqlalchemy as sa

TEST_COMMANDS = {
    "pytest": "pytest --tb=short --json-report --json-report-file=/tmp/test_results.json -q",
    "jest": "npx jest --json 2>/dev/null | tee /tmp/test_results.json",
    "cargo": "cargo test 2>&1",
    "go": "go test ./... 2>&1",
}

class SandboxTestArgs(BaseModel):
    task_id: str
    command: str = Field(
        default="auto",
        description="Test command to run, or 'auto' to detect from project type"
    )

class SandboxTestTool(BaseTool):
    name = "sandbox_test"
    description = (
        "Run the project test suite inside the sandbox. "
        "Returns structured pass/fail counts and failure details. "
        "Results are persisted to the coding_tasks record."
    )
    args_schema = SandboxTestArgs

    async def run(self, task_id: str, command: str = "auto", user=None) -> str:
        self.check_permissions(user)
        sandbox = await require_sandbox(task_id)

        if command == "auto":
            # Detect project type
            probe = await sandbox.process.executeCommand(
                "ls /workspace/repo | grep -E '(package.json|pytest.ini|setup.py|Cargo.toml|go.mod)'"
            )
            detected = probe.result.strip()
            if "package.json" in detected:
                command = TEST_COMMANDS["jest"]
            elif any(x in detected for x in ["pytest.ini", "setup.py"]):
                command = TEST_COMMANDS["pytest"]
            elif "Cargo.toml" in detected:
                command = TEST_COMMANDS["cargo"]
            elif "go.mod" in detected:
                command = TEST_COMMANDS["go"]
            else:
                return "Could not detect test runner. Pass an explicit command= argument."

        result = await sandbox.process.executeCommand(
            f"cd /workspace/repo && {command}"
        )
        output = result.result or ""

        # Parse counts from output (best-effort)
        passed = failed = 0
        m_pass = re.search(r"(\d+)\s+passed", output)
        m_fail = re.search(r"(\d+)\s+failed", output)
        if m_pass:
            passed = int(m_pass.group(1))
        if m_fail:
            failed = int(m_fail.group(1))

        # Persist to DB
        with get_session() as session:
            session.execute(sa.text("""
                UPDATE coding_tasks
                SET tests_passed=:p, tests_failed=:f, test_output=:out, updated_at=now()
                WHERE task_id=:tid
            """), {"p": passed, "f": failed, "out": output[:8000], "tid": task_id})
            session.commit()

        status_line = f"Tests: {passed} passed, {failed} failed (exit {result.exitCode})"
        if failed > 0:
            return f"{status_line}\n\n--- Failures ---\n{output}"
        return f"{status_line}\n\n{output[:2000]}"
```

---

### Tool: `SandboxDiffTool`
**File**: `bark-bot/app/tools/coding/sandbox_diff.py`

Captures the current diff, stores it in `coding_tasks`, and returns it for review. Call this before `sandbox_git_commit` to give the agent and user a chance to inspect changes.

```python
from pydantic import BaseModel, Field
from app.tools.base import BaseTool
from .sandbox import require_sandbox
from app.db import get_session
import sqlalchemy as sa

class SandboxDiffArgs(BaseModel):
    task_id: str
    stat_only: bool = Field(
        default=False,
        description="If true, return only --stat summary, not the full diff"
    )

class SandboxDiffTool(BaseTool):
    name = "sandbox_diff"
    description = (
        "Show the current git diff in the sandbox. "
        "Always call this before sandbox_git_commit to review what will be committed. "
        "Stores the diff in the coding_tasks record for the frontend diff viewer."
    )
    args_schema = SandboxDiffArgs

    async def run(self, task_id: str, stat_only: bool = False, user=None) -> str:
        self.check_permissions(user)
        sandbox = await require_sandbox(task_id)

        stat_result = await sandbox.process.executeCommand(
            "cd /workspace/repo && git diff --stat"
        )
        stat_text = stat_result.result.strip()

        if stat_only:
            return stat_text or "No changes."

        full_result = await sandbox.process.executeCommand(
            "cd /workspace/repo && git diff"
        )
        diff_text = full_result.result or ""

        # Extract changed file paths
        files_changed = [
            line.split("|")[0].strip()
            for line in stat_text.splitlines()
            if "|" in line
        ]

        with get_session() as session:
            session.execute(sa.text("""
                UPDATE coding_tasks
                SET diff_text=:diff, files_changed=:files, updated_at=now()
                WHERE task_id=:tid
            """), {
                "diff": diff_text[:50000],
                "files": files_changed,
                "tid": task_id,
            })
            session.commit()

        return f"--- Stat ---\n{stat_text}\n\n--- Diff ---\n{diff_text[:8000]}"
```

---

### Tool: `SandboxGitCommitTool`
**File**: `bark-bot/app/tools/coding/sandbox_git_commit.py`

Stages all changes and commits. Enforces conventional commits format.

```python
import re
from pydantic import BaseModel, Field
from app.tools.base import BaseTool
from .sandbox import require_sandbox
from app.db import get_session
import sqlalchemy as sa

CONVENTIONAL_COMMIT_RE = re.compile(
    r"^(feat|fix|chore|refactor|test|docs|style|perf|ci|build|revert)(\(.+\))?: .+"
)

class SandboxGitCommitArgs(BaseModel):
    task_id: str
    message: str = Field(..., description="Commit message. Must follow conventional commits: feat: / fix: / chore: etc.")

class SandboxGitCommitTool(BaseTool):
    name = "sandbox_git_commit"
    description = (
        "Stage all changes and commit in the sandbox. "
        "Always run sandbox_test and sandbox_diff before calling this. "
        "Message must use conventional commits format."
    )
    args_schema = SandboxGitCommitArgs

    async def run(self, task_id: str, message: str, user=None) -> str:
        self.check_permissions(user)

        if not CONVENTIONAL_COMMIT_RE.match(message):
            return (
                f"COMMIT BLOCKED: message does not follow conventional commits format.\n"
                f"Got: {message!r}\n"
                f"Expected format: 'feat: description' or 'fix(scope): description' etc."
            )

        sandbox = await require_sandbox(task_id)
        await sandbox.git.add("workspace/repo", ["."])
        response = await sandbox.git.commit(
            "workspace/repo", message, "BarkPack Coding Agent", "agent@barkpack"
        )
        sha = getattr(response, "sha", getattr(response, "SHA", "unknown"))

        with get_session() as session:
            session.execute(sa.text("""
                UPDATE coding_tasks
                SET commit_sha=:sha, updated_at=now()
                WHERE task_id=:tid
            """), {"sha": sha, "tid": task_id})
            session.commit()

        return f"Committed: {sha}\nMessage: {message}"
```

---

### Tool: `SandboxGitPushTool`
**File**: `bark-bot/app/tools/coding/sandbox_git_push.py`

Explicit push, separated from commit so the user and agent can review the diff and test results before changes leave the sandbox. Requires `check_permissions` — this is the most consequential operation in the toolkit.

```python
from pydantic import BaseModel, Field
from app.tools.base import BaseTool
from .sandbox import require_sandbox
from app.db import get_session
import sqlalchemy as sa

class SandboxGitPushArgs(BaseModel):
    task_id: str
    git_username: str = Field(default="")
    git_token: str = Field(default="")
    create_pr: bool = Field(
        default=False,
        description="If true, run `gh pr create` after pushing"
    )
    pr_title: str = Field(default="")
    pr_body: str = Field(default="")

class SandboxGitPushTool(BaseTool):
    name = "sandbox_git_push"
    description = (
        "Push commits from the sandbox to the remote. "
        "Only call this after sandbox_test confirms tests pass and "
        "sandbox_diff has been reviewed. This is irreversible."
    )
    args_schema = SandboxGitPushArgs

    async def run(self, task_id: str, git_username: str = "", git_token: str = "",
                  create_pr: bool = False, pr_title: str = "", pr_body: str = "",
                  user=None) -> str:
        self.check_permissions(user)

        sandbox = await require_sandbox(task_id)
        push_kwargs = {"path": "workspace/repo"}
        if git_username and git_token:
            push_kwargs.update(username=git_username, password=git_token)

        await sandbox.git.push(**push_kwargs)

        pr_url = None
        if create_pr and pr_title:
            pr_result = await sandbox.process.executeCommand(
                f'cd /workspace/repo && gh pr create --title "{pr_title}" --body "{pr_body}"'
            )
            # gh pr create prints the PR URL on success
            pr_url = pr_result.result.strip().splitlines()[-1] if pr_result.result else None

        with get_session() as session:
            session.execute(sa.text("""
                UPDATE coding_tasks
                SET status='complete', pr_url=:pr_url, updated_at=now()
                WHERE task_id=:tid
            """), {"pr_url": pr_url, "tid": task_id})
            session.commit()

        lines = ["Pushed successfully."]
        if pr_url:
            lines.append(f"PR created: {pr_url}")
        return "\n".join(lines)
```

---

### Tool: `SandboxReleaseTool`
**File**: `bark-bot/app/tools/coding/sandbox_release.py`

```python
from pydantic import BaseModel, Field
from app.tools.base import BaseTool
from .sandbox import release_sandbox
from app.db import get_session
import sqlalchemy as sa

class SandboxReleaseArgs(BaseModel):
    task_id: str

class SandboxReleaseTool(BaseTool):
    name = "sandbox_release"
    description = (
        "Delete the Daytona sandbox for a completed or abandoned task. "
        "Always call this when done, unless the user explicitly wants to keep the sandbox alive."
    )
    args_schema = SandboxReleaseArgs

    async def run(self, task_id: str, user=None) -> str:
        self.check_permissions(user)
        await release_sandbox(task_id)

        with get_session() as session:
            session.execute(sa.text("""
                UPDATE coding_tasks
                SET sandbox_status='deleted', updated_at=now()
                WHERE task_id=:tid
            """), {"tid": task_id})
            session.commit()

        return f"Sandbox released: task_id={task_id}"
```

---

## Step 5 — Register All Tools

**File**: `bark-bot/app/tools/registry.py` — surgical `edit`, do not rewrite

Read the file first. Then add all 12 imports and entries to `NATIVE_TOOLS`:

```python
from app.tools.coding.sandbox_create import SandboxCreateTool
from app.tools.coding.sandbox_bash import SandboxBashTool
from app.tools.coding.sandbox_read import SandboxReadTool
from app.tools.coding.sandbox_write import SandboxWriteTool
from app.tools.coding.sandbox_edit import SandboxEditTool
from app.tools.coding.sandbox_glob import SandboxGlobTool
from app.tools.coding.sandbox_grep import SandboxGrepTool
from app.tools.coding.sandbox_list import SandboxListTool
from app.tools.coding.sandbox_test import SandboxTestTool
from app.tools.coding.sandbox_diff import SandboxDiffTool
from app.tools.coding.sandbox_git_commit import SandboxGitCommitTool
from app.tools.coding.sandbox_git_push import SandboxGitPushTool
from app.tools.coding.sandbox_release import SandboxReleaseTool

NATIVE_TOOLS = {
    # ... existing entries ...
    "sandbox_create":     SandboxCreateTool,
    "sandbox_bash":       SandboxBashTool,
    "sandbox_read":       SandboxReadTool,
    "sandbox_write":      SandboxWriteTool,
    "sandbox_edit":       SandboxEditTool,
    "sandbox_glob":       SandboxGlobTool,
    "sandbox_grep":       SandboxGrepTool,
    "sandbox_list":       SandboxListTool,
    "sandbox_test":       SandboxTestTool,
    "sandbox_diff":       SandboxDiffTool,
    "sandbox_git_commit": SandboxGitCommitTool,
    "sandbox_git_push":   SandboxGitPushTool,
    "sandbox_release":    SandboxReleaseTool,
}
```

---

## Step 6 — Create the Skill YAML

**File**: `bark-bot/app/agents/coding_agent.yaml` *(new)*

```yaml
id: coding_agent
name: "Coding Agent"
system_prompt: |
  You are a senior software engineer operating inside BarkPack.
  You implement code changes in secure Daytona sandbox environments.
  You are methodical: read and understand before writing, work in small verifiable
  increments, test after every significant change, and never push broken code.

  ## Workflow — always in this order

  1. **sandbox_create** — start here. One sandbox per task. Use it to clone the repo.
  2. **Read the codebase** — use sandbox_glob, sandbox_grep, sandbox_read to understand
     the existing structure before writing anything. Log your findings with create_agent_post.
  3. **Implement** — use sandbox_edit for targeted changes, sandbox_write for new files.
     Prefer sandbox_edit. Never rewrite files you could edit surgically.
  4. **Test** — run sandbox_test after every significant change. Fix failures before continuing.
  5. **Review** — run sandbox_diff before committing. Confirm the diff is exactly what was intended.
  6. **Commit** — use sandbox_git_commit with a conventional commits message.
  7. **Push** — only after tests pass. Use sandbox_git_push with create_pr=true for non-trivial changes.
  8. **Release** — call sandbox_release when done, unless the user asks to keep the sandbox.

  ## Rules
  - Always use absolute paths inside the sandbox: /workspace/repo/path/to/file
  - Use conventional commits: feat:, fix:, chore:, refactor:, test:, docs:
  - If a task is ambiguous, ask for clarification before calling sandbox_create.
  - Scope tasks tightly. One sandbox per logical change set.
  - Use create_agent_post to log reasoning, dead ends, and summaries. Other agents read this.
  - Use search_agent_posts before starting to check if similar work was already done.

  ## Context compression
  When conversation history is compressed, the summary must include:
  - What was implemented or fixed
  - Files created, modified, deleted
  - Test results at last check (N passed, N failed)
  - Current git branch and last commit SHA
  - Active task_id and sandbox status
  - Remaining work and next steps
  - Any open questions or blockers

active_tools:
  - sandbox_create
  - sandbox_bash
  - sandbox_read
  - sandbox_write
  - sandbox_edit
  - sandbox_glob
  - sandbox_grep
  - sandbox_list
  - sandbox_test
  - sandbox_diff
  - sandbox_git_commit
  - sandbox_git_push
  - sandbox_release
  - create_agent_post
  - search_agent_posts
```

---

## Step 7 — Add Environment Variables

**File**: `bark-bot/.env.example` — `edit`, do not rewrite

Append:

```bash
# Daytona Sandbox (coding_agent skill)
DAYTONA_API_KEY=
DAYTONA_API_URL=https://app.daytona.io/api
DAYTONA_TARGET=us
CODING_AGENT_SNAPSHOT=swe-agent-base
```

---

## Step 8 — Write Tests

**File**: `bark-bot/tests/tools/test_coding_agent.py` *(new)*

All Daytona SDK calls are mocked. Tests verify: tool logic, permission gating, DB writes, and error handling. CI must pass without real credentials.

```python
"""Tests for coding agent sandbox tools. Daytona SDK is fully mocked."""
import pytest
from unittest.mock import AsyncMock, MagicMock, patch

@pytest.fixture
def mock_sandbox():
    sb = MagicMock()
    sb.id = "sandbox-abc123"
    sb.git.clone = AsyncMock()
    sb.git.add = AsyncMock()
    sb.git.commit = AsyncMock(return_value=MagicMock(sha="deadbeef"))
    sb.git.push = AsyncMock()
    sb.git.status = AsyncMock(return_value=MagicMock(
        currentBranch="feat/test", ahead=1, behind=0
    ))
    sb.fs.downloadFile = AsyncMock(return_value=b"def hello():\n    pass\n")
    sb.fs.uploadFile = AsyncMock()
    sb.fs.listFiles = AsyncMock(return_value=[
        MagicMock(name="src", isDir=True, size=0),
        MagicMock(name="README.md", isDir=False, size=1024),
    ])
    sb.fs.findFiles = AsyncMock(return_value=[
        MagicMock(file="/workspace/repo/src/app.py", line=1, content="def hello():")
    ])
    sb.process.executeCommand = AsyncMock(return_value=MagicMock(
        exitCode=0, result="3 passed, 0 failed"
    ))
    sb.delete = AsyncMock()
    return sb


@pytest.fixture
def mock_db(monkeypatch):
    """Mock the DB session so tests don't need Postgres."""
    session = MagicMock()
    session.__enter__ = MagicMock(return_value=session)
    session.__exit__ = MagicMock(return_value=False)
    monkeypatch.setattr("app.tools.coding.sandbox_create.get_session", lambda: session)
    monkeypatch.setattr("app.tools.coding.sandbox_test.get_session", lambda: session)
    monkeypatch.setattr("app.tools.coding.sandbox_diff.get_session", lambda: session)
    monkeypatch.setattr("app.tools.coding.sandbox_git_commit.get_session", lambda: session)
    monkeypatch.setattr("app.tools.coding.sandbox_git_push.get_session", lambda: session)
    monkeypatch.setattr("app.tools.coding.sandbox_release.get_session", lambda: session)
    return session


# ── sandbox_create ──────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_sandbox_create_registers_sandbox(mock_sandbox, mock_db):
    with patch("app.tools.coding.sandbox_create.get_client") as mc:
        mc.return_value.create = AsyncMock(return_value=mock_sandbox)
        from app.tools.coding.sandbox_create import SandboxCreateTool
        from app.tools.coding import sandbox as sb_module
        tool = SandboxCreateTool()
        result = await tool.run(
            task_id="t-001",
            task_description="Add hello endpoint",
            repo_url="https://github.com/org/repo.git",
        )
    assert "t-001" in result
    assert sb_module._sandboxes.get("t-001") is mock_sandbox
    mock_sandbox.git.clone.assert_called_once()


# ── sandbox_bash ────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_sandbox_bash_blocks_rm_rf(mock_sandbox):
    from app.tools.coding import sandbox as sb_module
    sb_module._sandboxes["t-002"] = mock_sandbox
    from app.tools.coding.sandbox_bash import SandboxBashTool
    tool = SandboxBashTool()
    result = await tool.run(task_id="t-002", command="rm -rf /workspace/repo")
    assert "BLOCKED" in result
    mock_sandbox.process.executeCommand.assert_not_called()


@pytest.mark.asyncio
async def test_sandbox_bash_runs_safe_command(mock_sandbox):
    from app.tools.coding import sandbox as sb_module
    sb_module._sandboxes["t-003"] = mock_sandbox
    from app.tools.coding.sandbox_bash import SandboxBashTool
    tool = SandboxBashTool()
    result = await tool.run(task_id="t-003", command="npm install")
    assert "3 passed" in result
    mock_sandbox.process.executeCommand.assert_called_once()


# ── sandbox_edit ────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_sandbox_edit_succeeds(mock_sandbox):
    from app.tools.coding import sandbox as sb_module
    sb_module._sandboxes["t-004"] = mock_sandbox
    from app.tools.coding.sandbox_edit import SandboxEditTool
    tool = SandboxEditTool()
    result = await tool.run(
        task_id="t-004",
        path="/workspace/repo/src/app.py",
        old_str="def hello():\n    pass",
        new_str='def hello():\n    return "hello"',
    )
    assert "Edited" in result
    mock_sandbox.fs.uploadFile.assert_called_once()


@pytest.mark.asyncio
async def test_sandbox_edit_fails_if_not_found(mock_sandbox):
    from app.tools.coding import sandbox as sb_module
    sb_module._sandboxes["t-005"] = mock_sandbox
    from app.tools.coding.sandbox_edit import SandboxEditTool
    tool = SandboxEditTool()
    result = await tool.run(
        task_id="t-005",
        path="/workspace/repo/src/app.py",
        old_str="this string does not exist",
        new_str="replacement",
    )
    assert "EDIT FAILED" in result
    mock_sandbox.fs.uploadFile.assert_not_called()


# ── sandbox_git_commit ──────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_commit_rejects_non_conventional_message(mock_sandbox, mock_db):
    from app.tools.coding import sandbox as sb_module
    sb_module._sandboxes["t-006"] = mock_sandbox
    from app.tools.coding.sandbox_git_commit import SandboxGitCommitTool
    tool = SandboxGitCommitTool()
    result = await tool.run(task_id="t-006", message="added some stuff")
    assert "COMMIT BLOCKED" in result
    mock_sandbox.git.commit.assert_not_called()


@pytest.mark.asyncio
async def test_commit_accepts_conventional_message(mock_sandbox, mock_db):
    from app.tools.coding import sandbox as sb_module
    sb_module._sandboxes["t-007"] = mock_sandbox
    from app.tools.coding.sandbox_git_commit import SandboxGitCommitTool
    tool = SandboxGitCommitTool()
    result = await tool.run(task_id="t-007", message="feat: add hello endpoint")
    assert "deadbeef" in result
    mock_sandbox.git.commit.assert_called_once()
```

Run tests:

```bash
cd bark-bot && uv run pytest tests/tools/test_coding_agent.py -v
```

All must pass.

---

## Step 9 — Verify Registration

```bash
cd bark-bot && uv run python -c "
from app.tools.registry import NATIVE_TOOLS
tools = [
    'sandbox_create','sandbox_bash','sandbox_read','sandbox_write','sandbox_edit',
    'sandbox_glob','sandbox_grep','sandbox_list','sandbox_test','sandbox_diff',
    'sandbox_git_commit','sandbox_git_push','sandbox_release',
]
for t in tools:
    assert t in NATIVE_TOOLS, f'Missing: {t}'
    print(f'✓ {t}')
print(f'All {len(tools)} tools registered.')
"
```

```bash
cd bark-bot && uv run python -c "
import yaml
with open('app/agents/coding_agent.yaml') as f:
    data = yaml.safe_load(f)
assert data['id'] == 'coding_agent'
assert len(data['active_tools']) == 15
print('✓ coding_agent.yaml valid,', len(data['active_tools']), 'tools')
"
```

---

## Step 10 — Integration Smoke Test

Only runs if `DAYTONA_API_KEY` is set. Safe to skip in CI.

```bash
cd bark-bot && uv run python -c "
import asyncio, os
if not os.getenv('DAYTONA_API_KEY'):
    print('DAYTONA_API_KEY not set — skipping live smoke test')
    exit(0)

from app.tools.coding.sandbox_create import SandboxCreateTool
from app.tools.coding.sandbox_bash import SandboxBashTool
from app.tools.coding.sandbox_read import SandboxReadTool
from app.tools.coding.sandbox_release import SandboxReleaseTool

async def main():
    task_id = 'smoke-001'

    r = await SandboxCreateTool().run(
        task_id=task_id,
        task_description='Smoke test',
        repo_url='https://github.com/anomalyco/opencode.git',
    )
    print('create:', r)

    r = await SandboxBashTool().run(task_id=task_id, command='ls /workspace/repo | head -5')
    print('bash:', r)

    r = await SandboxReadTool().run(task_id=task_id, path='/workspace/repo/README.md')
    print('read (first 200 chars):', r[:200])

    await SandboxReleaseTool().run(task_id=task_id)
    print('released.')

asyncio.run(main())
"
```

---

## Step 11 — Log Completion

```
create_agent_post(
  title="coding_agent skill added to BarkPack (native tools architecture)",
  body="""
    Architecture: native BarkPack tools backed by Daytona SDK.
    No OpenCode subprocess. All tool calls visible in BarkPack session DB.

    Files created:
      bark-bot/app/tools/coding/__init__.py
      bark-bot/app/tools/coding/sandbox.py          (lifecycle manager)
      bark-bot/app/tools/coding/sandbox_create.py
      bark-bot/app/tools/coding/sandbox_bash.py
      bark-bot/app/tools/coding/sandbox_read.py
      bark-bot/app/tools/coding/sandbox_write.py
      bark-bot/app/tools/coding/sandbox_edit.py
      bark-bot/app/tools/coding/sandbox_glob.py
      bark-bot/app/tools/coding/sandbox_grep.py
      bark-bot/app/tools/coding/sandbox_list.py
      bark-bot/app/tools/coding/sandbox_test.py
      bark-bot/app/tools/coding/sandbox_diff.py
      bark-bot/app/tools/coding/sandbox_git_commit.py
      bark-bot/app/tools/coding/sandbox_git_push.py
      bark-bot/app/tools/coding/sandbox_release.py
      bark-bot/app/agents/coding_agent.yaml
      bark-bot/tests/tools/test_coding_agent.py
      bark-bot/alembic/versions/{timestamp}_add_coding_tasks.py

    Files modified:
      bark-bot/app/tools/registry.py  (13 new entries)
      bark-bot/.env.example           (4 new vars)
      bark-bot/pyproject.toml         (daytonaio dep)

    Required env vars:
      DAYTONA_API_KEY, DAYTONA_API_URL, DAYTONA_TARGET, CODING_AGENT_SNAPSHOT

    Skill available via: load_skill("coding_agent")
    All 13 sandbox_* tools are in NATIVE_TOOLS and subject to check_permissions.
  """
)
```

---

## File Checklist

```
bark-bot/
├── alembic/versions/
│   └── {timestamp}_add_coding_tasks.py        [NEW]
├── app/
│   ├── agents/
│   │   └── coding_agent.yaml                  [NEW]
│   └── tools/
│       ├── registry.py                         [EDIT — 13 new entries]
│       └── coding/
│           ├── __init__.py                     [NEW]
│           ├── sandbox.py                      [NEW — lifecycle manager]
│           ├── sandbox_create.py               [NEW]
│           ├── sandbox_bash.py                 [NEW]
│           ├── sandbox_read.py                 [NEW]
│           ├── sandbox_write.py                [NEW]
│           ├── sandbox_edit.py                 [NEW]
│           ├── sandbox_glob.py                 [NEW]
│           ├── sandbox_grep.py                 [NEW]
│           ├── sandbox_list.py                 [NEW]
│           ├── sandbox_test.py                 [NEW]
│           ├── sandbox_diff.py                 [NEW]
│           ├── sandbox_git_commit.py           [NEW]
│           ├── sandbox_git_push.py             [NEW]
│           └── sandbox_release.py             [NEW]
├── tests/
│   └── tools/
│       └── test_coding_agent.py               [NEW]
├── .env.example                                [EDIT — 4 new vars]
└── pyproject.toml                              [EDIT — daytonaio dep]
```

---

## Constraints & Reminders

- Use `uv` for all Python operations, never `pip` directly.
- Use `edit` for surgical changes to existing files; `write` only for new files.
- All sandbox paths must be absolute: `/workspace/repo/...`
- `sandbox_bash` blocks sensitive patterns before they hit Daytona — never remove this guard.
- `sandbox_edit` requires `old_str` to match exactly once — always `sandbox_read` the file first.
- `sandbox_diff` must be called before `sandbox_git_commit` — enforce this in the agent's workflow, not just the docs.
- `sandbox_git_push` is the only tool that makes changes visible outside the sandbox — it gets the highest permission scrutiny.
- `coding_agent.yaml` is synced to S3 by `AgentLoader` on startup — no manual upload needed.
- Do not modify the orchestrator (`bark_bot`) or any existing tools. This is purely additive.
- OpenCode is not installed, not referenced, not a dependency. The `sandbox_*` tool designs are inspired by it, but the runtime is 100% BarkPack + Daytona.