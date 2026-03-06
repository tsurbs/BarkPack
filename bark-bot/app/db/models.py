from sqlalchemy import Column, String, Text, DateTime, ForeignKey, JSON
from pgvector.sqlalchemy import Vector
from datetime import datetime, timezone
import uuid

from app.db.session import Base

def generate_uuid():
    return str(uuid.uuid4())

def utcnow():
    # Return offset-naive datetime representing UTC
    return datetime.now(timezone.utc).replace(tzinfo=None)

class DBUser(Base):
    __tablename__ = "users"
    id = Column(String, primary_key=True, default=generate_uuid)
    email = Column(String, unique=True, index=True)
    name = Column(String)
    profile_data = Column(JSON, default=dict)
    
class Conversation(Base):
    __tablename__ = "conversations"
    id = Column(String, primary_key=True, default=generate_uuid)
    user_id = Column(String, ForeignKey("users.id"))
    created_at = Column(DateTime, default=utcnow)
    
class DBMessage(Base):
    __tablename__ = "messages"
    id = Column(String, primary_key=True, default=generate_uuid)
    conversation_id = Column(String, ForeignKey("conversations.id"))
    role = Column(String) # 'system', 'user', 'assistant', 'tool'
    content = Column(Text)
    created_at = Column(DateTime, default=utcnow)
    
class AgentPost(Base):
    __tablename__ = "agent_posts"
    id = Column(String, primary_key=True, default=generate_uuid)
    agent_id = Column(String)
    content = Column(Text)
    # Using pgvector to store an embedding of the content for semantic retrieval
    embedding = Column(Vector(1536))
    created_at = Column(DateTime, default=utcnow)

class APILog(Base):
    __tablename__ = "api_logs"
    id = Column(String, primary_key=True, default=generate_uuid)
    conversation_id = Column(String, ForeignKey("conversations.id"), nullable=True)
    event_type = Column(String) # 'openrouter_request', 'openrouter_response', 'tool_request', 'tool_response'
    payload = Column(Text) # JSON serialized data
    created_at = Column(DateTime, default=utcnow)

class ContextSummary(Base):
    __tablename__ = "context_summaries"
    id = Column(String, primary_key=True, default=generate_uuid)
    conversation_id = Column(String, ForeignKey("conversations.id"), index=True)
    summary = Column(Text)
    messages_summarized = Column(String)  # Integer count of messages compressed
    created_at = Column(DateTime, default=utcnow)

class DBTool(Base):
    __tablename__ = "tools"
    id = Column(String, primary_key=True, default=generate_uuid)
    name = Column(String, unique=True, index=True)
    description = Column(Text)
    tool_type = Column(String) # 'native', 'python', 'mcp'
    content = Column(Text)
    created_at = Column(DateTime, default=utcnow)
    updated_at = Column(DateTime, default=utcnow, onupdate=utcnow)
