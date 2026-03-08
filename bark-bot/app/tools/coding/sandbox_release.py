from pydantic import BaseModel
from typing import Optional
from sqlalchemy.ext.asyncio import AsyncSession
from app.tools.base import BaseTool
from app.models.user import User
from .sandbox import release_sandbox

class SandboxReleaseArgs(BaseModel):
    task_id: str

class SandboxReleaseTool(BaseTool):
    name = "sandbox_release"
    description = "Release/delete a sandbox when done."
    args_schema = SandboxReleaseArgs

    async def run(self, args: SandboxReleaseArgs, user: User, db: Optional[AsyncSession] = None) -> str:
        await release_sandbox(args.task_id)
        return f"Released sandbox for task {args.task_id!r}."
