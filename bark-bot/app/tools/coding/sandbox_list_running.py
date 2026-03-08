from typing import Optional
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from app.tools.base import BaseTool
from app.models.user import User
from .sandbox import get_client

class SandboxListRunningArgs(BaseModel):
    pass

class SandboxListRunningTool(BaseTool):
    name = "sandbox_list_running"
    description = "List all active/running Daytona sandboxes for the current organization."
    args_schema = SandboxListRunningArgs

    async def run(self, args: SandboxListRunningArgs, user: User, db: Optional[AsyncSession] = None) -> str:
        client = get_client()
        sandboxes = await client.list()
        
        if not sandboxes:
            return "No active sandboxes found."

        lines = ["Active Sandboxes:"]
        for sb in sandboxes:
            task_id = sb.labels.get("task_id", "N/A")
            lines.append(f"- Name: {sb.name} | ID: {sb.id} | State: {sb.state} | TaskID: {task_id}")
            
        return "\n".join(lines)
