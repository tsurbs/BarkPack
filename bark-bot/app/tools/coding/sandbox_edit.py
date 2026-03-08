import re
from typing import Optional
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession
from app.tools.base import BaseTool
from app.models.user import User
from .sandbox import require_sandbox

class SandboxEditArgs(BaseModel):
    task_id: str
    path: str
    old_str: str = Field(..., description="The exact string to be replaced")
    new_str: str = Field(..., description="The replacement string")

class SandboxEditTool(BaseTool):
    name = "sandbox_edit"
    description = "Perform a targeted string replacement in a file within the sandbox. old_str must match exactly once."
    args_schema = SandboxEditArgs

    async def run(self, args: SandboxEditArgs, user: User, db: Optional[AsyncSession] = None) -> str:
        sandbox = await require_sandbox(args.task_id)
        
        # Download, replace, upload
        content_bytes = await sandbox.fs.download_file(args.path)
        content = content_bytes.decode("utf-8")
        
        count = content.count(args.old_str)
        if count == 0:
            return f"Error: {args.old_str!r} not found in {args.path}"
        if count > 1:
            return f"Error: {args.old_str!r} found {count} times. Use a more unique segment."

        new_content = content.replace(args.old_str, args.new_str)
        await sandbox.fs.upload_file(new_content.encode("utf-8"), args.path)
        
        return f"Successfully edited {args.path}."
