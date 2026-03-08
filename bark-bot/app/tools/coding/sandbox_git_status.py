from pydantic import BaseModel
from typing import Optional
from sqlalchemy.ext.asyncio import AsyncSession
from app.tools.base import BaseTool
from app.models.user import User
from .sandbox import require_sandbox

class SandboxGitStatusArgs(BaseModel):
    task_id: str

class SandboxGitStatusTool(BaseTool):
    name = "sandbox_git_status"
    description = "Check git status in the sandbox."
    args_schema = SandboxGitStatusArgs

    async def run(self, args: SandboxGitStatusArgs, user: User, db: Optional[AsyncSession] = None) -> str:
        sandbox = await require_sandbox(args.task_id)
        result = await sandbox.process.exec("cd workspace/repo && git status")
        return result.result
