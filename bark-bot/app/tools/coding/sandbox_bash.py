import re
from typing import Optional
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from app.tools.base import BaseTool
from app.models.user import User
from .sandbox import require_sandbox

SENSITIVE_PATTERNS = [
    r"\brm\s+-rf\b",
    r"\bgit\s+reset\s+--hard\b",
]

class SandboxBashArgs(BaseModel):
    task_id: str
    command: str
    workdir: str = Field(default="/workspace/repo")

class SandboxBashTool(BaseTool):
    name = "sandbox_bash"
    description = "Run a shell command inside the coding sandbox."
    args_schema = SandboxBashArgs

    async def run(self, args: SandboxBashArgs, user: User, db: Optional[AsyncSession] = None) -> str:
        for pattern in SENSITIVE_PATTERNS:
            if re.search(pattern, args.command, re.IGNORECASE):
                return f"BLOCKED: sensitive pattern {pattern!r}."

        sandbox = await require_sandbox(args.task_id)
        result = await sandbox.process.exec(args.command, cwd=args.workdir)
        return f"Exit code: {result.exit_code}\n{result.result}"
