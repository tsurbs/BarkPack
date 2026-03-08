from typing import Optional
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from app.tools.base import BaseTool
from app.models.user import User
from .sandbox import get_client, register_sandbox

class SandboxStartArgs(BaseModel):
    task_id: str = Field(..., description="The task_id of the sandbox to start")

class SandboxStartTool(BaseTool):
    name = "sandbox_start"
    description = (
        "Start a stopped sandbox by task_id. "
        "Use this if you find a sandbox is stopped and you need to resume work."
    )
    args_schema = SandboxStartArgs

    async def run(self, args: SandboxStartArgs, user: User, db: Optional[AsyncSession] = None) -> str:
        client = get_client()
        sandboxes_resp = await client.list()
        sandboxes = sandboxes_resp.items
        
        target_sb = None
        for sb in sandboxes:
            if sb.labels.get("task_id") == args.task_id:
                target_sb = sb
                break
        
        if not target_sb:
            return f"Error: Could not find sandbox for task_id={args.task_id!r}"

        if target_sb.state == "started":
            return f"Sandbox {target_sb.name!r} is already started."

        await target_sb.start()
        await register_sandbox(args.task_id, target_sb)
        
        return f"Successfully started sandbox {target_sb.name!r} (ID: {target_sb.id}) for task {args.task_id!r}."
