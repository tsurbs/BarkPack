from pydantic import BaseModel
from typing import Optional
from sqlalchemy.ext.asyncio import AsyncSession
from app.tools.base import BaseTool
from app.models.user import User
from .sandbox import require_sandbox

class SandboxWriteArgs(BaseModel):
    task_id: str
    path: str
    content: str

class SandboxWriteTool(BaseTool):
    name = "sandbox_write"
    description = "Write a file to the sandbox."
    args_schema = SandboxWriteArgs

    async def run(self, args: SandboxWriteArgs, user: User, db: Optional[AsyncSession] = None) -> str:
        sandbox = await require_sandbox(args.task_id)
        await sandbox.fs.upload_file(args.content.encode("utf-8"), args.path)
        return f"Written: {args.path}"
