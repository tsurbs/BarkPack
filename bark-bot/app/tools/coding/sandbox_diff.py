import sqlalchemy as sa
from pydantic import BaseModel, Field
from typing import Optional
from sqlalchemy.ext.asyncio import AsyncSession
from app.tools.base import BaseTool
from app.models.user import User
from .sandbox import require_sandbox

class SandboxDiffArgs(BaseModel):
    task_id: str
    stat_only: bool = Field(default=False)

class SandboxDiffTool(BaseTool):
    name = "sandbox_diff"
    description = "Show the current git diff in the sandbox."
    args_schema = SandboxDiffArgs

    async def run(self, args: SandboxDiffArgs, user: User, db: Optional[AsyncSession] = None) -> str:
        sandbox = await require_sandbox(args.task_id)

        stat_cmd = "cd workspace/repo && git diff --stat"
        stat_result = await sandbox.process.exec(stat_cmd)
        stat_text = stat_result.result.strip() or "No changes."

        if args.stat_only:
            return stat_text

        full_cmd = "cd workspace/repo && git diff"
        full_result = await sandbox.process.exec(full_cmd)
        diff_text = full_result.result

        if db:
            await db.execute(sa.text("""
                UPDATE coding_tasks
                SET diff_text=:diff, updated_at=now()
                WHERE task_id=:tid
            """), {"diff": diff_text[:50000], "tid": args.task_id})
            await db.commit()

        return f"--- Stat ---\n{stat_text}\n\n--- Diff ---\n{diff_text[:8000]}"
