import asyncio
from sqlalchemy.ext.asyncio import create_async_engine

DATABASE_URL = "postgresql+asyncpg://postgres:HttXgWfRDBdZJmUoJjIqOQnjnLCAQjQG@viaduct.proxy.rlwy.net:19248/railway"

# Just append ssl=disable to see if Railway strictly REQUIRES it, or if it REJECTS it.
DATABASE_URL = DATABASE_URL + "?ssl=disable"

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
            print("Successfully connected!")
    except Exception as e:
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    asyncio.run(main())
