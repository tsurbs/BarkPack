from pydantic import BaseModel, Field
from typing import Optional
from sqlalchemy.ext.asyncio import AsyncSession
from app.models.user import User
from app.tools.base import BaseTool

class LoadSkillArgs(BaseModel):
    skill_id: str = Field(description="The ID of the skill to load.")
    reason: str = Field(description="Optional context for why this skill is being loaded.")

class LoadSkillTool(BaseTool):
    """
    A special tool that allows an agent to load a skill into its context.
    The orchestrator specifically looks for the __LOAD_SKILL__ string
    to perform the context augmentation.
    """
    name = "load_skill"
    description = "Load a specialized skill into your current context. Use this when you need additional tools or specific instructions to fulfill the user's request. Valid skills are the same as the agent IDs."
    args_schema = LoadSkillArgs
    
    async def run(self, args: LoadSkillArgs, user: User, db: Optional[AsyncSession] = None) -> str:
        # A sentinel string that the orchestrator interprets
        return f"__LOAD_SKILL__:{args.skill_id}:{args.reason}"
