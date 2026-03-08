from pydantic import BaseModel, Field
from typing import Optional
from sqlalchemy.ext.asyncio import AsyncSession
from app.tools.base import BaseTool
from app.models.user import User
from .sandbox import require_sandbox

class SandboxGlobArgs(BaseModel):
    task_id: str
    pattern: str
    root: str = Field(default="/workspace/repo")

class SandboxGlobTool(BaseTool):
    name = "sandbox_glob"
    description = "Find files matching a glob pattern in the sandbox."
    args_schema = SandboxGlobArgs

    async def run(self, args: SandboxGlobArgs, user: User, db: Optional[AsyncSession] = None) -> str:
        sandbox = await require_sandbox(args.task_id)
        # Use find for globbing
        cmd = f"find {args.root} -name {args.pattern!r}"
        result = await sandbox.process.exec(cmd)
        return result.result or "No matches."
