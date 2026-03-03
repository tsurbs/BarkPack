import asyncio
from sqlalchemy.ext.asyncio import create_async_engine

# Using psycopg instead of asyncpg
DATABASE_URL = "postgresql+psycopg://postgres:HttXgWfRDBdZJmUoJjIqOQnjnLCAQjQG@viaduct.proxy.rlwy.net:19248/railway"

print(f"Connecting to: {DATABASE_URL}")

async def main():
    try:
        engine = create_async_engine(
            DATABASE_URL, 
            echo=False,
            # Just bare minimum to test the TCP connect
        )
        print("Engine created. Attempting to connect...")
        async with engine.connect() as conn:
            print("Successfully connected with psycopg!")
    except Exception as e:
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    asyncio.run(main())
