from pydantic import BaseModel, Field
from typing import Optional
from sqlalchemy.ext.asyncio import AsyncSession
from app.models.user import User
from app.tools.base import BaseTool
from app.memory.vector_store import add_agent_post, search_agent_posts
from app.memory.history import list_user_conversations

class CreateAgentPostArgs(BaseModel):
    content: str = Field(description="The long-term note, artifact, or summary to persist.")

class CreateAgentPostTool(BaseTool):
    name = "create_agent_post"
    description = "Save a note or artifact to the shared Agent Post memory board for long-term semantic retrieval."
    args_schema = CreateAgentPostArgs
    
    async def run(self, args: CreateAgentPostArgs, user: User, db: Optional[AsyncSession] = None) -> str:
        if not db:
            return "Error: No database connection available to save the post."
            
        # Normally we'd use the agent's ID. Since tools don't inherently know their parent agent,
        # we'll represent the creator generically or pass via context.
        # For this prototype, we'll label it 'orchestrator' or base agent.
        await add_agent_post(db, agent_id="agent", content=args.content)
        return "Successfully saved to long-term memory."

class SearchAgentPostsArgs(BaseModel):
    query: str = Field(description="The semantic search query.")

class SearchAgentPostsTool(BaseTool):
    name = "search_agent_posts"
    description = "Semantically search past agent posts and long-term memory."
    args_schema = SearchAgentPostsArgs
    
    async def run(self, args: SearchAgentPostsArgs, user: User, db: Optional[AsyncSession] = None) -> str:
        if not db:
            return "Error: No database connection available for semantic search."
            
        posts = await search_agent_posts(db, args.query, limit=3)
        if not posts:
            return "No relevant past notes found."
            
        results = [f"- {p.content}" for p in posts]
        return "Found relevant memory artifacts:\n" + "\n".join(results)

class ListConversationsArgs(BaseModel):
    limit: int = Field(description="The maximum number of recent conversations to list.", default=10)

class ListPastConversationsTool(BaseTool):
    name = "list_past_conversations"
    description = "List the IDs and timestamps of the user's past conversations."
    args_schema = ListConversationsArgs
    
    async def run(self, args: ListConversationsArgs, user: User, db: Optional[AsyncSession] = None) -> str:
        if not db:
            return "Error: No database connection available."
            
        convs = await list_user_conversations(db, user.id, limit=args.limit)
        if not convs:
            return "No past conversations found for this user."
            
        results = [f"- ID: {c.id} | Date: {c.created_at}" for c in convs]
        return "Your recent conversations:\n" + "\n".join(results)

class ReadConversationArgs(BaseModel):
    conversation_id: str = Field(description="The ID of the conversation to read.")
    limit: int = Field(description="The maximum number of recent messages to retrieve.", default=50)

class ReadConversationTool(BaseTool):
    name = "read_conversation"
    description = "Read the raw message transcript of a past conversation by its ID."
    args_schema = ReadConversationArgs
    
    async def run(self, args: ReadConversationArgs, user: User, db: Optional[AsyncSession] = None) -> str:
        if not db:
            return "Error: No database connection available."
            
        from app.memory.history import get_conversation_history
        history = await get_conversation_history(db, args.conversation_id, limit=args.limit)
        
        if not history:
            return f"No conversation found with ID {args.conversation_id}."
            
        log = []
        for msg in history:
            log.append(f"[{msg.created_at}] {msg.role.upper()}: {msg.content}")
            
        return f"Transcript of conversation {args.conversation_id}:\n\n" + "\n\n".join(log)
