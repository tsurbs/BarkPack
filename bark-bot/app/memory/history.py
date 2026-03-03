from typing import List, Optional
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from app.db.models import Conversation, DBMessage, DBUser, APILog
import json

async def get_or_create_user(session: AsyncSession, user_id: str, email: str = None, name: str = None) -> DBUser:
    result = await session.execute(select(DBUser).where(DBUser.id == user_id))
    user = result.scalar_one_or_none()
    
    if not user:
        user = DBUser(id=user_id, email=email, name=name)
        session.add(user)
        await session.commit()
    
    return user

async def get_or_create_conversation(session: AsyncSession, conv_id: str, user_id: str) -> Conversation:
    result = await session.execute(select(Conversation).where(Conversation.id == conv_id))
    conv = result.scalar_one_or_none()
    
    if not conv:
        conv = Conversation(id=conv_id, user_id=user_id)
        session.add(conv)
        await session.commit()
        await session.refresh(conv)
        
    return conv

async def list_user_conversations(session: AsyncSession, user_id: str, limit: int = 10) -> List[Conversation]:
    result = await session.execute(
        select(Conversation)
        .where(Conversation.user_id == user_id)
        .order_by(Conversation.created_at.desc())
        .limit(limit)
    )
    return list(result.scalars().all())

async def add_message(session: AsyncSession, conv_id: str, role: str, content: str) -> DBMessage:
    msg = DBMessage(conversation_id=conv_id, role=role, content=content)
    session.add(msg)
    await session.commit()
    return msg

async def get_conversation_history(session: AsyncSession, conv_id: str, limit: int = 50) -> List[DBMessage]:
    result = await session.execute(
        select(DBMessage)
        .where(DBMessage.conversation_id == conv_id)
        .order_by(DBMessage.created_at.asc())
        .limit(limit)
    )
    return list(result.scalars().all())

async def log_api_event(session: AsyncSession, conv_id: str, event_type: str, payload_dict: dict) -> APILog:
    if not session:
        return None
    log_entry = APILog(
        conversation_id=conv_id,
        event_type=event_type,
        payload=json.dumps(payload_dict, default=str)
    )
    session.add(log_entry)
    await session.commit()
    return log_entry
