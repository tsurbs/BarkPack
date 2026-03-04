import json
from sqlalchemy.ext.asyncio import AsyncSession
from app.models.user import User
from app.memory.history import get_conversation_history
from app.core.llm import generate_response

async def generate_user_profile(db: AsyncSession, user_id: str, conversation_id: str) -> str:
    """
    Summarize a user's preferences based on their recent conversation history.
    This creates the long-term User Profile memory.
    """
    history = await get_conversation_history(db, conversation_id, limit=50)
    if not history:
        return "No recent history available to summarize."
        
    chat_text = "\n".join([f"{msg.role}: {msg.content}" for msg in history])
    
    prompt = f"""
    Analyze the following conversation and extract any core preferences, facts, or instructions 
    the user explicitly mentioned about themselves or how they like things done.
    Keep it concise and focus only on long-term facts.
    
    Conversation:
    {chat_text}
    """
    
    response = await generate_response([{"role": "user", "content": prompt}], model="z-ai/glm-5")
    summary = response.get("content", "")
    
    # In a full implementation, we would save this `summary` to a UserProfile table 
    # or semantic vector store tied to the user_id. 
    # For now, we will just return it.
    print(f"[Memory] Generated profile for user {user_id}: {summary}")
    return summary
