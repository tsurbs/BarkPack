import asyncio
import os
import sys

# Add the root project directory to the path so we can import 'app'
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from sqlalchemy.ext.asyncio import create_async_engine
from sqlalchemy import text
from app.db.models import Base
from app.db.session import engine, DATABASE_URL

async def init_db():
    print(f"Connecting to database...")
    
    async with engine.begin() as conn:
        print("Creating pgvector extension (requires superuser/postgres user)...")
        # vector extension is required for the AgentPost embedding column
        await conn.execute(text("CREATE EXTENSION IF NOT EXISTS vector"))
        
        print("Creating tables from SQLAlchemy models...")
        # Create all tables (users, conversations, messages, agent_posts)
        await conn.run_sync(Base.metadata.create_all)
        
    print("Database initialization complete! ✅")
    await engine.dispose()

if __name__ == "__main__":
    asyncio.run(init_db())
