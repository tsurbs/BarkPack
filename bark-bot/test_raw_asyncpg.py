import asyncio
import asyncpg
import ssl
import certifi

DATABASE_URL = "postgres://postgres:HttXgWfRDBdZJmUoJjIqOQnjnLCAQjQG@viaduct.proxy.rlwy.net:19248/railway"

async def main():
    try:
        # Create a default SSL context
        ssl_context = ssl.create_default_context(cafile=certifi.where())
        ssl_context.check_hostname = False
        ssl_context.verify_mode = ssl.CERT_NONE

        print(f"Attempting raw asyncpg connect to: {DATABASE_URL}")
        conn = await asyncpg.connect(DATABASE_URL, ssl=ssl_context)
        print("Successfully connected via raw asyncpg!")
        await conn.close()
    except Exception as e:
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    asyncio.run(main())
