import asyncio
from sqlalchemy.ext.asyncio import create_async_engine

async def main():
    try:
        engine = create_async_engine(
            "postgresql+asyncpg://postgres:postgres@localhost:5432/barkbot",
            connect_args={
                "prepared_statement_cache_size": 0,
                "statement_cache_size": 0
            }
        )
        async with engine.connect() as conn:
            print("Successfully connected with both args.")
    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    asyncio.run(main())
