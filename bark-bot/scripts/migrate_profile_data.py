import asyncio
import os
import sys

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from sqlalchemy.ext.asyncio import create_async_engine
from sqlalchemy import text
from app.db.session import DATABASE_URL

async def migrate():
    engine = create_async_engine(DATABASE_URL, echo=False)
    async with engine.begin() as conn:
        print("Altering users table to add profile_data JSON column...")
        try:
            await conn.execute(text("ALTER TABLE users ADD COLUMN profile_data JSON;"))
            print("Success!")
        except Exception as e:
            print(f"Skipping or failed: {e}")
            
    await engine.dispose()

if __name__ == "__main__":
    asyncio.run(migrate())
