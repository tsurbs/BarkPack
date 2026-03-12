from sqlalchemy import Column, String, Text, DateTime, ForeignKey, Boolean, JSON, Integer
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

class CodingTask(Base):
    __tablename__ = "coding_tasks"
    id = Column(String, primary_key=True, default=generate_uuid)
    task_id = Column(String, unique=True, index=True) # Public/Agent-facing ID (e.g. task-abc)
    status = Column(String, default="pending") # pending, running, complete, failed, abandoned
    source = Column(String) # Slack, CLI, GitHub
    task_description = Column(Text)
    work_product = Column(Text) # Resulting PR URL or branch
    repo_url = Column(String)
    branch = Column(String)
    sandbox_id = Column(String)
    sandbox_status = Column(String) # created, running, stopped, deleted
    media_artifacts = Column(JSON, default=list) # List of S3 URLs (screenshots/videos)
    test_results = Column(JSON, default=dict) # Structured test output
    token_cost = Column(Integer, default=0)
    # Semantic search over tasks
    task_embedding = Column(Vector(1536))
    diff_text = Column(Text) # Captured git diff
    files_changed = Column(JSON, default=list)
    commit_sha = Column(String)
    created_at = Column(DateTime, default=utcnow)
    updated_at = Column(DateTime, default=utcnow, onupdate=utcnow)

class DBRole(Base):
    __tablename__ = "roles"
    id = Column(String, primary_key=True, default=generate_uuid)
    name = Column(String, unique=True, index=True)
    description = Column(Text)
    created_at = Column(DateTime, default=utcnow)
    
class DBUserRole(Base):
    __tablename__ = "user_roles"
    id = Column(String, primary_key=True, default=generate_uuid)
    user_id = Column(String, ForeignKey("user.id", ondelete="cascade"), index=True)
    role_id = Column(String, ForeignKey("roles.id", ondelete="cascade"), index=True)
    created_at = Column(DateTime, default=utcnow)

class DBSurfaceCredential(Base):
    __tablename__ = "surface_credentials"
    id = Column(String, primary_key=True, default=generate_uuid)
    user_id = Column(String, ForeignKey("user.id", ondelete="cascade"), index=True)
    surface = Column(String, index=True) # e.g. 'slack', 'github', 'linear'
    token = Column(Text) # The actual encrypted credential/token
    created_at = Column(DateTime, default=utcnow)
    updated_at = Column(DateTime, default=utcnow, onupdate=utcnow)
