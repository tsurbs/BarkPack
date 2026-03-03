import os
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession
from sqlalchemy.orm import declarative_base

# Fallback to localhost if not set in .env
DATABASE_URL = os.getenv("DATABASE_URL", "postgresql+asyncpg://postgres:postgres@localhost:5432/barkbot")

# Create the async engine
engine = create_async_engine(DATABASE_URL, echo=False)

# Create an async session maker
AsyncSessionLocal = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

Base = declarative_base()

async def get_db():
    """
    FastAPI dependency for injecting the Async SQLAlchemy session.
    """
    async with AsyncSessionLocal() as session:
        yield session
