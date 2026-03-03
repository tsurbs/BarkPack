from pydantic import BaseModel, Field
from typing import Optional
from sqlalchemy.ext.asyncio import AsyncSession
from app.models.user import User
from app.tools.base import BaseTool

class HandoffArgs(BaseModel):
    target_agent_id: str = Field(description="The ID of the agent to hand off to.")
    handover_message: str = Field(description="Context or instructions passed to the target agent.")

class HandoffTool(BaseTool):
    """
    A special tool that allows an agent to hand off control.
    The orchestrator specifically looks for the HANDING_OFF_TO string
    to perform the context switch.
    """
    name = "handoff"
    description = "Hand off the conversation to another specialized agent. Use this when the user's request is better suited for a different agent."
    args_schema = HandoffArgs
    
    async def run(self, args: HandoffArgs, user: User, db: Optional[AsyncSession] = None) -> str:
        # A sentinel string that the orchestrator interprets
        return f"__HANDOFF__:{args.target_agent_id}:{args.handover_message}"
