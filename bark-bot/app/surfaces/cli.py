import asyncio
import uuid
from app.core.orchestrator import handle_chat_request
from app.models.schemas import ChatRequest, Message
from app.db.session import AsyncSessionLocal

async def start_cli():
    print("Welcome to Bark Bot CLI! Type 'exit' to quit.")
    print("This is the simple CLI surface for local testing.")
    print("-" * 50)
    
    chat_history = []
    
    # Generate a dummy user ID and conversation ID for this CLI session
    cli_user_id = str(uuid.uuid4())
    cli_conversation_id = str(uuid.uuid4())
    
    while True:
        try:
            user_input = input("\nYou: ")
        except (KeyboardInterrupt, EOFError):
            break
            
        if user_input.lower() in ["exit", "quit"]:
            break
            
        chat_history.append(Message(role="user", content=user_input))
        
        current_agent = "bark_bot"
        req = ChatRequest(messages=[Message(role="user", content=user_input)], user_id=cli_user_id, agent_id=current_agent)
        
        print("\nBark Bot is thinking...")
        try:
            while True:
                async with AsyncSessionLocal() as db:
                    resp = await handle_chat_request(req, db=db, conversation_id=cli_conversation_id)
                
                print(f"\n[{current_agent}]: {resp.message.content}")
                
                if resp.agent_id and resp.agent_id != current_agent:
                    current_agent = resp.agent_id
                    req.agent_id = current_agent
                    req.messages = [] # Don't resubmit the user message on handoff
                    print(f"\n[{current_agent}] received handoff and is thinking...")
                    continue
                else:
                    break
        except Exception as e:
            print(f"\nError processing request: {str(e)}")

if __name__ == "__main__":
    asyncio.run(start_cli())
