"""Tool system for extending the chatbot's capabilities."""

import threading
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any, Callable


@dataclass
class Tool(ABC):
    """Base class for chatbot tools."""

    name: str
    description: str
    parameters: dict[str, Any] = field(default_factory=dict)

    @abstractmethod
    async def execute(self, **kwargs: Any) -> str:
        """Execute the tool with the given arguments."""
        pass

    def to_openai_schema(self) -> dict[str, Any]:
        """Convert to OpenAI function calling schema."""
        return {
            "type": "function",
            "function": {
                "name": self.name,
                "description": self.description,
                "parameters": self.parameters,
            },
        }


# Global lock for sync tool calls — libraries like the Google API client and
# httplib2/protobuf are NOT thread-safe, so parallel asyncio.to_thread calls
# can corrupt memory.  This serializes sync tool execution while still
# allowing truly async tools to run concurrently.
_sync_tool_lock = threading.Lock()


@dataclass
class FunctionTool(Tool):
    """A tool that wraps a simple function."""

    func: Callable[..., Any] | None = None

    async def execute(self, **kwargs: Any) -> str:
        """Execute the wrapped function."""
        if self.func is None:
            return "Error: No function defined for this tool"

        import asyncio
        import inspect

        if inspect.iscoroutinefunction(self.func):
            # Already async — await directly
            result = await self.func(**kwargs)
        else:
            # Sync function — run in a thread with a lock to prevent
            # concurrent access to non-thread-safe libraries (e.g. Google API)
            def _locked_call() -> Any:
                with _sync_tool_lock:
                    return self.func(**kwargs)  # type: ignore[misc]

            result = await asyncio.to_thread(_locked_call)

        return str(result)


class ToolRegistry:
    """Registry for managing available tools."""

    def __init__(self) -> None:
        self._tools: dict[str, Tool] = {}

    def register(self, tool: Tool) -> None:
        """Register a tool."""
        self._tools[tool.name] = tool

    def get(self, name: str) -> Tool | None:
        """Get a tool by name."""
        return self._tools.get(name)

    def list_tools(self) -> list[Tool]:
        """List all registered tools."""
        return list(self._tools.values())

    def to_openai_schema(self) -> list[dict[str, Any]]:
        """Get all tools in OpenAI function calling schema."""
        return [tool.to_openai_schema() for tool in self._tools.values()]


# Global registry instance
_registry = ToolRegistry()


def get_registry() -> ToolRegistry:
    """Get the global tool registry."""
    return _registry


def tool(
    name: str,
    description: str,
    parameters: dict[str, Any] | None = None,
) -> Callable[[Callable[..., Any]], Callable[..., Any]]:
    """Decorator to register a function as a tool.

    Usage:
        @tool(
            name="get_weather",
            description="Get the current weather for a location",
            parameters={
                "type": "object",
                "properties": {
                    "location": {"type": "string", "description": "City name"}
                },
                "required": ["location"]
            }
        )
        async def get_weather(location: str) -> str:
            return f"Weather in {location}: Sunny, 72°F"
    """

    def decorator(func: Callable[..., Any]) -> Callable[..., Any]:
        func_tool = FunctionTool(
            name=name,
            description=description,
            parameters=parameters or {"type": "object", "properties": {}},
            func=func,
        )
        _registry.register(func_tool)
        return func

    return decorator
