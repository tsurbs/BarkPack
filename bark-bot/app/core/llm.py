import os
import json
from openai import AsyncOpenAI
from dotenv import load_dotenv
from sqlalchemy.ext.asyncio import AsyncSession
from app.memory.history import log_api_event

load_dotenv()

OPENROUTER_BASE_URL = "https://openrouter.ai/api/v1"
OPENROUTER_API_KEY = os.getenv("OPENROUTER_API_KEY", "")

# Initialize the async OpenAI client pointing to OpenRouter
client = AsyncOpenAI(
    base_url=OPENROUTER_BASE_URL,
    api_key=OPENROUTER_API_KEY,
)

async def generate_response(messages: list[dict], tools: list[dict] = None, model: str = "moonshotai/kimi-k2.5", db: AsyncSession = None, conversation_id: str = None) -> dict:
    """
    Generate a response using OpenRouter, supporting tools.
    """
    if not OPENROUTER_API_KEY:
        return {"content": "Error: OPENROUTER_API_KEY is not set."}

    try:
        kwargs = {
            "model": model,
            "messages": messages
        }
        if tools:
            kwargs["tools"] = tools

        if db and conversation_id:
            await log_api_event(db, conversation_id, 'openrouter_request', kwargs)

        print(f"\n[DEBUG LLM REQUEST] Model: {kwargs['model']}, Messages: {json.dumps(kwargs['messages'], indent=2)}\n")
        response = await client.chat.completions.create(**kwargs)
        
        if db and conversation_id:
            await log_api_event(db, conversation_id, 'openrouter_response', response.model_dump())
            
        choice = response.choices[0]
        
        # Return a dictionary representing the message (content + tool_calls)
        msg_dict = {"content": choice.message.content or ""}
        if choice.message.tool_calls:
            msg_dict["tool_calls"] = []
            for tc in choice.message.tool_calls:
                msg_dict["tool_calls"].append({
                    "id": tc.id,
                    "type": "function",
                    "function": {
                        "name": tc.function.name,
                        "arguments": tc.function.arguments
                    }
                })
        return msg_dict
    except Exception as e:
        return {"content": f"Error communicating with OpenRouter: {str(e)}"}
