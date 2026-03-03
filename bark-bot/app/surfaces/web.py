from fastapi import APIRouter, HTTPException, Depends
from pydantic import BaseModel
from typing import List, Optional
import time

from app.core.orchestrator import handle_chat_request
from app.models.schemas import ChatRequest, Message as InternalMessage
from app.core.auth import get_current_user
from app.models.user import User

router = APIRouter(prefix="/v1")

# OpenAI-compatible request schemas
class OpenAIChatMessage(BaseModel):
    role: str
    content: str
    name: Optional[str] = None

class OpenAIChatCompletionRequest(BaseModel):
    model: str
    messages: List[OpenAIChatMessage]
    temperature: Optional[float] = 1.0
    stream: Optional[bool] = False

# OpenAI-compatible response schemas
class OpenAIChatChoice(BaseModel):
    index: int
    message: OpenAIChatMessage
    finish_reason: str = "stop"

class OpenAIChatCompletionResponse(BaseModel):
    id: str = "chatcmpl-barkbot"
    object: str = "chat.completion"
    created: int
    model: str
    choices: List[OpenAIChatChoice]

@router.post("/chat/completions", response_model=OpenAIChatCompletionResponse)
async def chat_completions(req: OpenAIChatCompletionRequest, user: User = Depends(get_current_user)):
    """
    OpenAI-compatible chat completion endpoint.
    Acts as the Web/API surface for Bark Bot.
    """
    # 1. Convert OpenAI format to internal ChatRequest format
    internal_messages = [
        InternalMessage(role=m.role, content=m.content) for m in req.messages
    ]
    
    # We pass the authenticated user's ID down to the ChatRequest
    internal_req = ChatRequest(messages=internal_messages, user_id=user.id)
    
    # 2. Process through orchestrator
    try:
        internal_resp = await handle_chat_request(internal_req)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Orchestrator Error: {str(e)}")
        
    # 3. Convert back to OpenAI format
    resp_message = OpenAIChatMessage(
        role=internal_resp.message.role,
        content=internal_resp.message.content
    )
    
    return OpenAIChatCompletionResponse(
        created=int(time.time()),
        model=req.model,
        choices=[
            OpenAIChatChoice(
                index=0,
                message=resp_message
            )
        ]
    )
