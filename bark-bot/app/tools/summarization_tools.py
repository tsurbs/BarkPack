import json
from pydantic import BaseModel, Field
from typing import Optional
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from app.models.user import User
from app.db.models import DBUser
from app.tools.base import BaseTool
from app.memory.history import get_conversation_history
from app.core.llm import generate_response

class SummarizeConversationArgs(BaseModel):
    conversation_id: str = Field(description="The ID of the conversation to summarize.")
    summary_instructions: str = Field(description="Specific instructions on what to extract from the conversation logs.", default="")

class SummarizeConversationTool(BaseTool):
    name = "summarize_conversation"
    description = "Read the recent history of a conversation and generate a condensed summary."
    args_schema = SummarizeConversationArgs
    
    async def run(self, args: SummarizeConversationArgs, user: User, db: Optional[AsyncSession] = None) -> str:
        if not db:
            return "Error: Database connection required for this tool."
            
        history = await get_conversation_history(db, args.conversation_id)
        if not history:
             return f"No conversation found with ID {args.conversation_id}"
             
        log_text = "\n".join([f"{msg.role}: {msg.content}" for msg in history[-30:]]) # Limit to last 30 for context Window
        
        prompt = f"""
        Please summarize the key takeaways, facts, and user preferences from the following conversation log.
        Instructions: {args.summary_instructions}
        
        Log:
        {log_text}
        """
        
        response = await generate_response([{"role": "user", "content": prompt}])
        return response.get("content", "Error generating summary.")

class UpdateUserProfileArgs(BaseModel):
    user_id: str = Field(description="The ID of the user to update.")
    profile_data: dict = Field(description="A dictionary of key/value properties representing attributes, preferences, or facts about the user.")

class UpdateUserProfileTool(BaseTool):
    name = "update_user_profile"
    description = "Updates the structured JSON profile of a user in the database with new extracted facts."
    args_schema = UpdateUserProfileArgs
    
    async def run(self, args: UpdateUserProfileArgs, user: User, db: Optional[AsyncSession] = None) -> str:
        if not db:
             return "Error: Database connection required."
             
        result = await db.execute(select(DBUser).where(DBUser.id == args.user_id))
        db_user = result.scalar_one_or_none()
        
        if not db_user:
             return f"Error: User {args.user_id} not found."
             
        # Merge dictionaries
        current_data = db_user.profile_data or {}
        current_data.update(args.profile_data)
        
        db_user.profile_data = current_data
        await db.commit()
        
        return f"Successfully updated User {args.user_id} profile. Current profile: {json.dumps(current_data)}"
