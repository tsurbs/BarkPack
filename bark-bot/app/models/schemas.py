from pydantic import BaseModel
from typing import List, Optional

class Message(BaseModel):
    role: str
    content: str

class Attachment(BaseModel):
    filename: str
    file_path: str
    content_type: Optional[str] = None

class ChatRequest(BaseModel):
    messages: List[Message]
    agent_id: Optional[str] = None
    user_id: Optional[str] = None

class ChatResponse(BaseModel):
    message: Message
    agent_id: Optional[str] = None
    no_reply: bool = False
    attachments: Optional[List[Attachment]] = None
