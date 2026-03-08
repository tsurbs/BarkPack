from pydantic import BaseModel, Field
from typing import Optional
from sqlalchemy.ext.asyncio import AsyncSession
from app.tools.base import BaseTool
from app.models.user import User
from .sandbox import require_sandbox

class SandboxGrepArgs(BaseModel):
    task_id: str
    pattern: str
    path: str = Field(default="/workspace/repo")

class SandboxGrepTool(BaseTool):
    name = "sandbox_grep"
    description = "Search for a pattern in the sandbox using ripgrep."
    args_schema = SandboxGrepArgs

    async def run(self, args: SandboxGrepArgs, user: User, db: Optional[AsyncSession] = None) -> str:
        sandbox = await require_sandbox(args.task_id)
        result = await sandbox.process.exec(f"rg --line-number {args.pattern!r} {args.path}")
        return result.result or "No matches."
