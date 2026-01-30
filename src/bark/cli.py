"""CLI entrypoint for Bark."""

import argparse
import asyncio

from bark.core import ChatBot


async def interactive_chat() -> None:
    """Run an interactive chat session."""
    print("Bark - ScottyLabs ChatBot")
    print("Type 'quit' or 'exit' to end the session.\n")

    async with ChatBot() as bot:
        conversation = bot.create_conversation()

        while True:
            try:
                user_input = input("You: ").strip()
            except (EOFError, KeyboardInterrupt):
                print("\nGoodbye!")
                break

            if not user_input:
                continue

            if user_input.lower() in ("quit", "exit"):
                print("Goodbye!")
                break

            try:
                print("\nBark: ", end="", flush=True)
                async for chunk in bot.stream_chat(user_input, conversation):
                    print(chunk, end="", flush=True)
                print("\n")
            except Exception as e:
                print(f"\nError: {e}\n")


def main() -> None:
    """Main CLI entrypoint."""
    parser = argparse.ArgumentParser(description="Bark - ScottyLabs ChatBot")
    parser.add_argument(
        "--serve",
        action="store_true",
        help="Start the HTTP server instead of interactive mode",
    )
    parser.add_argument(
        "--port",
        type=int,
        default=8000,
        help="Port for HTTP server (default: 8000)",
    )

    args = parser.parse_args()

    if args.serve:
        from bark.server import main as serve_main

        serve_main()
    else:
        asyncio.run(interactive_chat())


if __name__ == "__main__":
    main()
