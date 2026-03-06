from sqlalchemy import Column, String, Text, DateTime, ForeignKey, Boolean, JSON
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

# --- BetterAuth Standard Tables ---

class DBUserAuth(Base):
    """BetterAuth user table. Note: 'user' instead of 'users' to match BetterAuth defaults."""
    __tablename__ = "user"
    id = Column(Text, primary_key=True, default=generate_uuid)
    name = Column(Text, nullable=False)
    email = Column(Text, nullable=False, unique=True)
    email_verified = Column(Boolean, default=False, nullable=False)
    image = Column(Text, nullable=True)
    created_at = Column(DateTime, default=utcnow, nullable=False)
    updated_at = Column(DateTime, default=utcnow, onupdate=utcnow, nullable=False)

class DBSession(Base):
    __tablename__ = "session"
    id = Column(Text, primary_key=True, default=generate_uuid)
    expires_at = Column(DateTime, nullable=False)
    token = Column(Text, nullable=False, unique=True)
    created_at = Column(DateTime, default=utcnow, nullable=False)
    updated_at = Column(DateTime, default=utcnow, onupdate=utcnow, nullable=False)
    ip_address = Column(Text, nullable=True)
    user_agent = Column(Text, nullable=True)
    user_id = Column(Text, ForeignKey("user.id", ondelete="cascade"), nullable=False, index=True)

class DBAccount(Base):
    __tablename__ = "account"
    id = Column(Text, primary_key=True, default=generate_uuid)
    account_id = Column(Text, nullable=False)
    provider_id = Column(Text, nullable=False)
    user_id = Column(Text, ForeignKey("user.id", ondelete="cascade"), nullable=False, index=True)
    access_token = Column(Text, nullable=True)
    refresh_token = Column(Text, nullable=True)
    id_token = Column(Text, nullable=True)
    access_token_expires_at = Column(DateTime, nullable=True)
    refresh_token_expires_at = Column(DateTime, nullable=True)
    scope = Column(Text, nullable=True)
    password = Column(Text, nullable=True)
    created_at = Column(DateTime, default=utcnow, nullable=False)
    updated_at = Column(DateTime, default=utcnow, onupdate=utcnow, nullable=False)

class DBVerification(Base):
    __tablename__ = "verification"
    id = Column(Text, primary_key=True, default=generate_uuid)
    identifier = Column(Text, nullable=False, index=True)
    value = Column(Text, nullable=False)
    expires_at = Column(DateTime, nullable=False)
    created_at = Column(DateTime, default=utcnow, nullable=False)
    updated_at = Column(DateTime, default=utcnow, onupdate=utcnow, nullable=False)
