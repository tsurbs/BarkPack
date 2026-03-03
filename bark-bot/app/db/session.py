import os
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession
from sqlalchemy.orm import declarative_base

# Fallback to localhost if not set in .env
DATABASE_URL = os.getenv("DATABASE_URL", "postgresql+psycopg://postgres:postgres@localhost:5432/barkbot")

# Railway internal PostgreSQL network doesn't support SSL, so we must disable it explicitly
# if psycopg attempts to upgrade the connection.
if DATABASE_URL.startswith("postgres://"):
    DATABASE_URL = DATABASE_URL.replace("postgres://", "postgresql+psycopg://", 1)
elif DATABASE_URL.startswith("postgresql://"):
    DATABASE_URL = DATABASE_URL.replace("postgresql://", "postgresql+psycopg://", 1)

if "postgresql+asyncpg://" in DATABASE_URL:
    DATABASE_URL = DATABASE_URL.replace("postgresql+asyncpg://", "postgresql+psycopg://", 1)

if "sslmode=" not in DATABASE_URL.lower() and "localhost" not in DATABASE_URL.lower():
    join_char = "&" if "?" in DATABASE_URL else "?"
    # Require SSL for all remote connections to prevent immediate drops and HTTP rejections
    DATABASE_URL = f"{DATABASE_URL}{join_char}sslmode=require"

# Create the async engine
engine = create_async_engine(
    DATABASE_URL, 
    echo=False,
    pool_pre_ping=True,  # Test connections before handing them out
    pool_recycle=300     # Recycle connections older than 5 minutes
)

# Create an async session maker
AsyncSessionLocal = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

Base = declarative_base()

async def get_db():
    """
    FastAPI dependency for injecting the Async SQLAlchemy session.
    """
    async with AsyncSessionLocal() as session:
        yield session
