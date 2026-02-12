"""Main ChatBot class that coordinates conversations."""

from dataclasses import dataclass, field
from typing import Any, AsyncGenerator

from bark.core.config import Settings, get_settings
from bark.core.openrouter import Message, OpenRouterClient, ToolCallCallback
from bark.core.tools import ToolRegistry, get_registry


def _load_memories() -> str:
    """Load all memories and format them for context injection."""
    parts = []
    
    # Load from new hierarchical memory system
    try:
        from bark.memory.memory_system import get_memory_system
        memory = get_memory_system()
        
        # Always include core.md content
        core_content = memory.get_core_content()
        if core_content:
            parts.append(core_content)
        
        # Add summary of memory structure
        summary = memory.get_all_memories_summary()
        if summary:
            parts.append(summary)
    except Exception:
        pass
    
    # Also load legacy key-value memories for backwards compatibility
    try:
        from bark.tools.memory_tools import _load_memory
        legacy_memory = _load_memory()
        if legacy_memory:
            lines = ["", "**Legacy memories:**"]
            for key, value in legacy_memory.items():
                lines.append(f"- {key}: {value}")
            parts.append("\n".join(lines))
    except Exception:
        pass
    
    if not parts:
        return ""
    
    return "\n\n".join(parts)



@dataclass
class Conversation:
    """Manages a single conversation's state."""

    messages: list[Message] = field(default_factory=list)
    system_prompt: str = ""

    def __post_init__(self) -> None:
        """Initialize with system prompt if provided."""
        if self.system_prompt and not self.messages:
            self.messages.append(Message(role="system", content=self.system_prompt))

    def add_user_message(self, content: str) -> None:
        """Add a user message to the conversation."""
        self.messages.append(Message(role="user", content=content))

    def add_assistant_message(self, content: str) -> None:
        """Add an assistant message to the conversation."""
        self.messages.append(Message(role="assistant", content=content))

    def get_messages(self) -> list[Message]:
        """Get all messages in the conversation."""
        return self.messages.copy()
    
    def update_system_with_memories(self) -> None:
        """Update the system message with current memories."""
        memories = _load_memories()
        if not memories:
            return
        
        # Find and update system message, or add one
        for i, msg in enumerate(self.messages):
            if msg.role == "system":
                # Strip old memories section if present
                content = msg.content or ""
                if "**Your stored memories:**" in content:
                    content = content.split("**Your stored memories:**")[0].rstrip()
                self.messages[i] = Message(role="system", content=content + memories)
                return
        
        # No system message found, add one
        self.messages.insert(0, Message(role="system", content=memories))


@dataclass
class ChatBot:
    """Main chatbot interface.

    Usage:
        async with ChatBot() as bot:
            response = await bot.chat("Hello!")
            print(response)
    """

    settings: Settings = field(default_factory=get_settings)
    registry: ToolRegistry = field(default_factory=get_registry)
    _client: OpenRouterClient | None = None

    async def __aenter__(self) -> "ChatBot":
        """Enter async context."""
        self._client = OpenRouterClient(
            settings=self.settings,
            registry=self.registry,
        )
        await self._client.__aenter__()
        return self

    async def __aexit__(self, *args) -> None:
        """Exit async context."""
        if self._client:
            await self._client.__aexit__(*args)

    def create_conversation(
        self,
        system_prompt: str | None = None,
        system_prompt_addendum: str | None = None,
    ) -> Conversation:
        """Create a new conversation.

        Args:
            system_prompt: Optional custom system prompt. Uses default if not provided.
            system_prompt_addendum: Optional addendum to append to the system prompt.
                Useful for integration-specific instructions (e.g., Slack formatting).
        """
        prompt = system_prompt or self.settings.system_prompt
        if system_prompt_addendum:
            prompt = f"{prompt}\n\n{system_prompt_addendum}"
        return Conversation(
            system_prompt=prompt,
        )

    async def chat(
        self,
        message: str,
        conversation: Conversation | None = None,
        on_tool_call: ToolCallCallback | None = None,
    ) -> str:
        """Send a message and get a response.

        Args:
            message: The user's message
            conversation: Optional conversation to continue. Creates new one if not provided.

        Returns:
            The assistant's response text
        """
        if not self._client:
            raise RuntimeError("ChatBot not initialized. Use 'async with' context.")

        # Create or use existing conversation
        if conversation is None:
            conversation = self.create_conversation()

        # Inject current memories into system prompt
        conversation.update_system_with_memories()

        # Add user message
        conversation.add_user_message(message)

        # Get response from OpenRouter
        response = await self._client.chat(
            conversation.get_messages(), on_tool_call=on_tool_call
        )

        # Add response to conversation
        content = response.content or ""
        conversation.add_assistant_message(content)

        return content

    async def stream_chat(
        self,
        message: str,
        conversation: Conversation | None = None,
    ) -> AsyncGenerator[str, None]:
        """Send a message and get a streaming response.

        Args:
            message: The user's message
            conversation: Optional conversation to continue. Creates new one if not provided.

        Yields:
            The assistant's response chunks
        """
        if not self._client:
            raise RuntimeError("ChatBot not initialized. Use 'async with' context.")

        # Create or use existing conversation
        if conversation is None:
            conversation = self.create_conversation()

        # Inject current memories into system prompt
        conversation.update_system_with_memories()

        # Add user message
        conversation.add_user_message(message)

        # Get streaming response from OpenRouter
        full_content = ""
        async for chunk in self._client.stream_chat(conversation.get_messages()):
            full_content += chunk
            yield chunk

        # Add response to conversation
        conversation.add_assistant_message(full_content)

    async def simple_chat(self, message: str) -> str:
        """Send a single message without conversation history.

        Useful for one-off questions.
        """
        if not self._client:
            raise RuntimeError("ChatBot not initialized. Use 'async with' context.")

        # Include memories in system prompt
        memories = _load_memories()
        system_content = self.settings.system_prompt + memories

        messages = [
            Message(role="system", content=system_content),
            Message(role="user", content=message),
        ]

        response = await self._client.chat(messages)
        return response.content or ""

