import os
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession
from sqlalchemy.orm import declarative_base

# Fallback to localhost if not set in .env
DATABASE_URL = os.getenv("DATABASE_URL", "postgresql+asyncpg://postgres:postgres@localhost:5432/barkbot")

# Railway internal PostgreSQL network doesn't support SSL, so we must disable it explicitly
# if asyncpg attempts to upgrade the connection.
if DATABASE_URL.startswith("postgres://"):
    DATABASE_URL = DATABASE_URL.replace("postgres://", "postgresql+asyncpg://", 1)
elif DATABASE_URL.startswith("postgresql://"):
    DATABASE_URL = DATABASE_URL.replace("postgresql://", "postgresql+asyncpg://", 1)

if "ssl=" not in DATABASE_URL.lower() and "localhost" not in DATABASE_URL.lower():
    join_char = "&" if "?" in DATABASE_URL else "?"
    if "railway.internal" in DATABASE_URL.lower():
        DATABASE_URL = f"{DATABASE_URL}{join_char}ssl=disable"
    else:
        # Require SSL for all other remote connections to prevent immediate drops
        DATABASE_URL = f"{DATABASE_URL}{join_char}ssl=require"

# Create the async engine
engine = create_async_engine(
    DATABASE_URL, 
    echo=False,
    pool_pre_ping=True,  # Test connections before handing them out
    pool_recycle=300,    # Recycle connections older than 5 minutes
    connect_args={
        "server_settings": {
            "tcp_keepalives_idle": "60"
        },
        "statement_cache_size": 0, # Fix for PgBouncer / Transaction poolers
        "prepared_statement_cache_size": 0
    }
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
