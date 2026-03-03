import asyncio
from sqlalchemy.ext.asyncio import create_async_engine

# The production DATABASE_URL retrieved from Railway
DATABASE_URL = "postgresql://postgres:HttXgWfRDBdZJmUoJjIqOQnjnLCAQjQG@viaduct.proxy.rlwy.net:19248/railway"

# Simulate the parsing logic in app/db/session.py
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

print(f"Connecting to: {DATABASE_URL}")

async def main():
    try:
        engine = create_async_engine(
            DATABASE_URL, 
            echo=False,
            pool_pre_ping=True,
            pool_recycle=300,
            connect_args={
                "server_settings": {
                    "tcp_keepalives_idle": "60"
                },
                "statement_cache_size": 0,
                "prepared_statement_cache_size": 0
            }
        )
        print("Engine created. Attempting to connect...")
        async with engine.connect() as conn:
            print("Successfully connected!")
    except Exception as e:
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    asyncio.run(main())
