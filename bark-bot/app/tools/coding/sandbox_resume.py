from typing import Optional
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from app.tools.base import BaseTool
from app.models.user import User
from .sandbox import get_client, register_sandbox

class SandboxResumeArgs(BaseModel):
    task_id: str = Field(..., description="The task_id of the sandbox to resume")
    sandbox_id: Optional[str] = Field(None, description="Optional explicit sandbox_id if task_id lookup fails")

class SandboxResumeTool(BaseTool):
    name = "sandbox_resume"
    description = (
        "Attach to an existing sandbox by task_id. "
        "Use this if the bot restarted or if you need to re-engage with a previously created environment."
    )
    args_schema = SandboxResumeArgs

    async def run(self, args: SandboxResumeArgs, user: User, db: Optional[AsyncSession] = None) -> str:
        client = get_client()
        sandboxes = await client.list()
        
        target_sb = None
        for sb in sandboxes:
            if sb.labels.get("task_id") == args.task_id:
                target_sb = sb
                break
            if args.sandbox_id and sb.id == args.sandbox_id:
                target_sb = sb
                break
        
        if not target_sb:
            return f"Error: Could not find sandbox for task_id={args.task_id!r}"

        # If it's stopped, start it
        if target_sb.state != "started":
            await target_sb.start()

        await register_sandbox(args.task_id, target_sb)
        
        return f"Successfully resumed sandbox {target_sb.name!r} (ID: {target_sb.id}) for task {args.task_id!r}."
