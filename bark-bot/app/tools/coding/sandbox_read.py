from pydantic import BaseModel
from typing import Optional
from sqlalchemy.ext.asyncio import AsyncSession
from app.tools.base import BaseTool
from app.models.user import User
from .sandbox import require_sandbox

class SandboxReadArgs(BaseModel):
    task_id: str
    path: str

class SandboxReadTool(BaseTool):
    name = "sandbox_read"
    description = "Read a file from the sandbox."
    args_schema = SandboxReadArgs

    async def run(self, args: SandboxReadArgs, user: User, db: Optional[AsyncSession] = None) -> str:
        sandbox = await require_sandbox(args.task_id)
        content = await sandbox.fs.download_file(args.path)
        return content.decode("utf-8", errors="replace") if isinstance(content, bytes) else str(content)
