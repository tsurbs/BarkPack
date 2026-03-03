import numpy as np
from typing import List
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from app.db.models import AgentPost

async def get_embedding(text: str) -> List[float]:
    """
    Generate an embedding vector.
    MOCK IMPLEMENTATION: Returns a random normalized vector of length 1536.
    In production, call an Embedding API (e.g. OpenAI text-embedding-ada-002, or a local HuggingFace model).
    """
    vector = np.random.rand(1536)
    vector = vector / np.linalg.norm(vector)
    return vector.tolist()

async def add_agent_post(db: AsyncSession, agent_id: str, content: str) -> AgentPost:
    """Save an artifact or note to long-term semantic memory."""
    embedding = await get_embedding(content)
    post = AgentPost(agent_id=agent_id, content=content, embedding=embedding)
    db.add(post)
    await db.commit()
    await db.refresh(post)
    return post

async def search_agent_posts(db: AsyncSession, query: str, limit: int = 5) -> List[AgentPost]:
    """Retrieve structurally similar posts from memory using pgvector cosine distance."""
    query_embedding = await get_embedding(query)
    
    # pgvector provides the cosine_distance method on Vector columns
    query_exec = select(AgentPost).order_by(AgentPost.embedding.cosine_distance(query_embedding)).limit(limit)
    result = await db.execute(query_exec)
    
    return list(result.scalars().all())
