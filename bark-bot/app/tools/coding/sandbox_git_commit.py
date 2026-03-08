import sqlalchemy as sa
from pydantic import BaseModel, Field
from typing import Optional
from sqlalchemy.ext.asyncio import AsyncSession
from app.tools.base import BaseTool
from app.models.user import User
from .sandbox import require_sandbox

class SandboxGitCommitArgs(BaseModel):
    task_id: str
    message: str = Field(..., description="Commit message")

class SandboxGitCommitTool(BaseTool):
    name = "sandbox_git_commit"
    description = "Commit all staged changes in the sandbox."
    args_schema = SandboxGitCommitArgs

    async def run(self, args: SandboxGitCommitArgs, user: User, db: Optional[AsyncSession] = None) -> str:
        sandbox = await require_sandbox(args.task_id)
        
        # Git config check/setup if needed for commit
        await sandbox.process.exec("git config --global user.email 'barkbot@example.com'")
        await sandbox.process.exec("git config --global user.name 'BarkBot'")
        
        # Add all and commit
        await sandbox.process.exec("cd workspace/repo && git add .")
        result = await sandbox.process.exec(f"cd workspace/repo && git commit -m {args.message!r}")
        
        return f"Commit result (Exit {result.exit_code}):\n{result.result}"
