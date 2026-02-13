"""Tool system for extending the chatbot's capabilities."""

import logging
import threading
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any, Callable

logger = logging.getLogger(__name__)


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

        # Log activity for the observability dashboard
        _log_tool_activity(self.name, kwargs)

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


# ---------------------------------------------------------------------------
# Activity logging helpers
# ---------------------------------------------------------------------------

# Map tool names to human-friendly action labels and committee extraction logic
_TOOL_ACTION_MAP: dict[str, str] = {
    "memory_write": "Memory saved",
    "write_memory": "Memory saved",
    "memory_read": "Memory recalled",
    "read_memory": "Memory recalled",
    "memory_search": "Memory searched",
    "memory_grep": "Memory searched",
    "memory_list": "Memory listed",
    "memory_delete": "Memory deleted",
    "delete_memory": "Memory deleted",
    "memory_move": "Memory moved",
    "memory_create_folder": "Folder created",
    "search_wiki": "Wiki queried",
    "search_notion": "Notion queried",
    "search_drive": "Drive searched",
    "refresh_context": "Context refreshed",
    "gmail_search": "Gmail searched",
    "gmail_read": "Email read",
    "gmail_send": "Email sent",
    "gmail_list_labels": "Gmail labels listed",
    "calendar_list_events": "Calendar read",
    "calendar_create_event": "Calendar event created",
    "calendar_list_calendars": "Calendars listed",
    "drive_list_files": "Drive accessed",
    "drive_create_folder": "Drive folder created",
    "drive_get_file_content": "Drive file read",
    "docs_get": "Doc read",
    "docs_create": "Doc created",
    "sheets_read": "Sheets read",
    "sheets_write": "Sheets updated",
    "firecrawl_scrape": "Web scraped",
    "firecrawl_crawl": "Web crawled",
}

# Tools that shouldn't be logged (internal / noisy)
_SKIP_TOOLS = {"no_reply"}


def _log_tool_activity(tool_name: str, kwargs: dict[str, Any]) -> None:
    """Log a tool execution to the activity logger."""
    if tool_name in _SKIP_TOOLS:
        return

    try:
        from bark.core.activity_logger import get_activity_logger

        al = get_activity_logger()
        action = _TOOL_ACTION_MAP.get(tool_name, f"Tool: {tool_name}")

        # Build a detail string from the kwargs
        detail = _build_detail(tool_name, kwargs)

        # Extract committee if present
        committee = kwargs.get("committee", "")
        if not committee and "folder" in kwargs and kwargs["folder"]:
            # e.g. folder="tech" or folder="tech/subfolder"
            committee = str(kwargs["folder"]).split("/")[0]
        if not committee and "path" in kwargs and kwargs["path"]:
            parts = str(kwargs["path"]).split("/")
            if len(parts) >= 2:
                committee = parts[0]

        al.log(action=action, detail=detail, committee=committee)
    except Exception:
        # Never let activity logging break tool execution
        logger.debug("Failed to log activity for tool %s", tool_name, exc_info=True)


def _build_detail(tool_name: str, kwargs: dict[str, Any]) -> str:
    """Build a human-readable detail string for a tool call."""
    if tool_name in ("memory_write", "write_memory"):
        filename = kwargs.get("filename", kwargs.get("key", ""))
        committee = kwargs.get("committee", "")
        if committee:
            return f"{committee}/{filename}"
        return str(filename)
    elif tool_name in ("memory_read", "read_memory"):
        return str(kwargs.get("path", kwargs.get("key", "")))
    elif tool_name in ("memory_search", "memory_grep"):
        return f'Search: "{kwargs.get("query", "")}"'
    elif tool_name == "memory_list":
        folder = kwargs.get("folder", "")
        return f"Listed {folder or 'root'}"
    elif tool_name in ("memory_delete", "delete_memory"):
        return f"Deleted {kwargs.get('path', kwargs.get('key', ''))}"
    elif tool_name == "memory_move":
        return f"{kwargs.get('src', '')} → {kwargs.get('dst', '')}"
    elif tool_name in ("search_wiki", "search_notion", "search_drive"):
        return f'Search: "{kwargs.get("query", "")}"'
    elif tool_name == "gmail_search":
        return f'Search: "{kwargs.get("query", "")}"'
    elif tool_name == "gmail_send":
        return f"To: {kwargs.get('to', '')}"
    elif tool_name in ("calendar_list_events", "calendar_list_calendars"):
        return "Fetched calendar data"
    elif tool_name == "calendar_create_event":
        return f"Event: {kwargs.get('summary', '')}"
    elif tool_name in ("drive_list_files", "drive_get_file_content"):
        return str(kwargs.get("folder_id", kwargs.get("file_id", "")))
    elif tool_name in ("docs_get", "docs_create"):
        return str(kwargs.get("document_id", kwargs.get("title", "")))
    elif tool_name in ("sheets_read", "sheets_write"):
        return str(kwargs.get("spreadsheet_id", ""))
    elif tool_name in ("firecrawl_scrape", "firecrawl_crawl"):
        return str(kwargs.get("url", ""))

    # Fallback: show first meaningful kwarg value
    for k, v in kwargs.items():
        if v and k not in ("content",):
            return f"{k}: {str(v)[:80]}"
    return tool_name


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
