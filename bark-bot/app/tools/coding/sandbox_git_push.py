import sqlalchemy as sa
from pydantic import BaseModel, Field
from typing import Optional
from sqlalchemy.ext.asyncio import AsyncSession
from app.tools.base import BaseTool
from app.models.user import User
from .sandbox import require_sandbox

class SandboxGitPushArgs(BaseModel):
    task_id: str
    remote: str = Field(default="origin")
    branch: str = Field(default="main")

class SandboxGitPushTool(BaseTool):
    name = "sandbox_git_push"
    description = "Push committed changes to remote."
    args_schema = SandboxGitPushArgs

    async def run(self, args: SandboxGitPushArgs, user: User, db: Optional[AsyncSession] = None) -> str:
        sandbox = await require_sandbox(args.task_id)
        await sandbox.git.push("workspace/repo")
        
        if db:
            await db.execute(sa.text("""
                UPDATE coding_tasks
                SET status='complete', updated_at=now()
                WHERE task_id=:tid
            """), {"tid": args.task_id})
            await db.commit()

        return "Successfully pushed."
