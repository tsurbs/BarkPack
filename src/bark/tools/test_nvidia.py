import asyncio
from bark.core.chatbot import ChatBot

async def main():
    print("Testing Nvidia API integration...")
    try:
        async with ChatBot() as bot:
            print("ChatBot initialized.")
            response = await bot.chat("Hello, are you working?")
            print(f"Response: {response}")
    except Exception as e:
        print(f"Error: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    asyncio.run(main())
