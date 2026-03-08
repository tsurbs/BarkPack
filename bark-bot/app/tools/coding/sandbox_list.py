from pydantic import BaseModel, Field
from typing import Optional
from sqlalchemy.ext.asyncio import AsyncSession
from app.tools.base import BaseTool
from app.models.user import User
from .sandbox import require_sandbox

class SandboxListArgs(BaseModel):
    task_id: str
    path: str = Field(default="workspace/repo")

class SandboxListTool(BaseTool):
    name = "sandbox_list"
    description = "List files in a sandbox path."
    args_schema = SandboxListArgs

    async def run(self, args: SandboxListArgs, user: User, db: Optional[AsyncSession] = None) -> str:
        sandbox = await require_sandbox(args.task_id)
        files = await sandbox.fs.list_files(args.path)
        lines = []
        for f in files:
            marker = "/" if f.is_dir else ""
            lines.append(f"{'d' if f.is_dir else '-'}  {f.name}{marker}  ({f.size} bytes)")
        return "\n".join(lines) if lines else f"(empty directory: {args.path})"
