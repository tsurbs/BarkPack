from pydantic import BaseModel
from typing import List, Optional

class Message(BaseModel):
    role: str
    content: str

class ChatRequest(BaseModel):
    messages: List[Message]
    agent_id: Optional[str] = None
    user_id: Optional[str] = None

class ChatResponse(BaseModel):
    message: Message
    agent_id: Optional[str] = None
