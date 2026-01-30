"""OpenRouter API client for chat completions with tool support."""

import json
from dataclasses import dataclass, field
from typing import Any, AsyncGenerator

import httpx

from bark.core.config import Settings, get_settings
from bark.core.tools import ToolRegistry, get_registry


@dataclass
class Message:
    """A chat message."""

    role: str  # "system", "user", "assistant", or "tool"
    content: str | None = None
    tool_calls: list[dict[str, Any]] | None = None
    tool_call_id: str | None = None
    name: str | None = None

    def to_dict(self) -> dict[str, Any]:
        """Convert to API format."""
        msg: dict[str, Any] = {"role": self.role}

        if self.content is not None:
            msg["content"] = self.content

        if self.tool_calls is not None:
            msg["tool_calls"] = self.tool_calls

        if self.tool_call_id is not None:
            msg["tool_call_id"] = self.tool_call_id

        if self.name is not None:
            msg["name"] = self.name

        return msg


@dataclass
class OpenRouterClient:
    """Async client for OpenRouter API."""

    settings: Settings = field(default_factory=get_settings)
    registry: ToolRegistry = field(default_factory=get_registry)
    _client: httpx.AsyncClient | None = None

    async def __aenter__(self) -> "OpenRouterClient":
        """Enter async context."""
        self._client = httpx.AsyncClient(
            base_url=self.settings.openrouter_base_url,
            headers={
                "Authorization": f"Bearer {self.settings.openrouter_api_key}",
                "Content-Type": "application/json",
                "HTTP-Referer": "https://scottylabs.org",
                "X-Title": "Bark ChatBot",
            },
            timeout=60.0,
        )
        return self

    async def __aexit__(self, *args: Any) -> None:
        """Exit async context."""
        if self._client:
            await self._client.aclose()

    async def chat(
        self,
        messages: list[Message],
        model: str | None = None,
    ) -> Message:
        """Send a chat completion request and handle tool calls.

        This method will automatically execute tool calls and continue
        the conversation until a final response is received.
        """
        if not self._client:
            raise RuntimeError("Client not initialized. Use 'async with' context.")

        model = model or self.settings.openrouter_model
        print("Using model: ", model)
        conversation = list(messages)  # Copy to avoid mutating input

        while True:
            # Build request payload
            payload: dict[str, Any] = {
                "model": model,
                "messages": [m.to_dict() for m in conversation],
            }

            # Add tools if available
            tools = self.registry.to_openai_schema()
            if tools:
                payload["tools"] = tools
                payload["tool_choice"] = "auto"

            # Make request
            response = await self._client.post("/chat/completions", json=payload)
            response.raise_for_status()
            data = response.json()

            # Parse response
            choice = data["choices"][0]
            message = choice["message"]

            # Check if we're done
            if choice.get("finish_reason") == "stop" or not message.get("tool_calls"):
                return Message(
                    role="assistant",
                    content=message.get("content", ""),
                )

            # Handle tool calls
            assistant_msg = Message(
                role="assistant",
                content=message.get("content"),
                tool_calls=message["tool_calls"],
            )
            conversation.append(assistant_msg)

            # Execute each tool call
            for tool_call in message["tool_calls"]:
                tool_name = tool_call["function"]["name"]
                # Handle empty/missing arguments (e.g., refresh_context with no params)
                args_str = tool_call["function"].get("arguments", "{}") or "{}"
                tool_args = json.loads(args_str)

                tool = self.registry.get(tool_name)
                if tool:
                    print(f"\n[Tool Call] {tool_name}({args_str})")
                    try:
                        result = await tool.execute(**tool_args)
                        print(f"[Tool Result] {result[:200]}{'...' if len(result) > 200 else ''}")
                    except Exception as e:
                        result = f"Error executing tool: {e}"
                        print(f"[Tool Error] {result}")
                else:
                    result = f"Unknown tool: {tool_name}"
                    print(f"[Tool Error] {result}")

                # Add tool result to conversation
                tool_msg = Message(
                    role="tool",
                    content=result,
                    tool_call_id=tool_call["id"],
                    name=tool_name,
                )
                conversation.append(tool_msg)

            # Continue loop to get final response

    async def stream_chat(
        self,
        messages: list[Message],
        model: str | None = None,
    ) -> AsyncGenerator[str, None]:
        """Send a chat completion request with streaming and handle tool calls.

        This method will automatically execute tool calls and continue
        the conversation until a final response is received.
        """
        if not self._client:
            raise RuntimeError("Client not initialized. Use 'async with' context.")

        model = model or self.settings.openrouter_model
        conversation = list(messages)  # Copy to avoid mutating input

        while True:
            # Build request payload
            payload: dict[str, Any] = {
                "model": model,
                "messages": [m.to_dict() for m in conversation],
                "stream": True,
            }

            # Add tools if available
            tools = self.registry.to_openai_schema()
            if tools:
                payload["tools"] = tools
                payload["tool_choice"] = "auto"

            # Make request
            full_content = ""
            tool_calls: list[dict[str, Any]] = []

            async with self._client.stream("POST", "/chat/completions", json=payload) as response:
                response.raise_for_status()
                async for line in response.aiter_lines():
                    if not line.startswith("data: "):
                        continue

                    data_str = line[6:]
                    if data_str == "[DONE]":
                        break

                    try:
                        data = json.loads(data_str)
                    except json.JSONDecodeError:
                        continue

                    if not data.get("choices"):
                        continue

                    delta = data["choices"][0].get("delta", {})

                    # Handle content
                    if "content" in delta and delta["content"]:
                        content = delta["content"]
                        full_content += content
                        yield content

                    # Handle tool calls
                    if "tool_calls" in delta:
                        for tool_call_delta in delta["tool_calls"]:
                            index = tool_call_delta.get("index", 0)
                            while len(tool_calls) <= index:
                                tool_calls.append({"id": "", "type": "function", "function": {"name": "", "arguments": ""}})
                            
                            if "id" in tool_call_delta:
                                tool_calls[index]["id"] += tool_call_delta["id"]
                            if "function" in tool_call_delta:
                                fn_delta = tool_call_delta["function"]
                                if "name" in fn_delta:
                                    tool_calls[index]["function"]["name"] += fn_delta["name"]
                                if "arguments" in fn_delta:
                                    tool_calls[index]["function"]["arguments"] += fn_delta["arguments"]

            # After stream finishes, check if we had tool calls
            if not tool_calls:
                return  # Final response reached

            # Handle tool calls
            assistant_msg = Message(
                role="assistant",
                content=full_content if full_content else None,
                tool_calls=tool_calls,
            )
            conversation.append(assistant_msg)

            # Execute each tool call
            for tool_call in tool_calls:
                tool_name = tool_call["function"]["name"]
                args_str = tool_call["function"].get("arguments", "{}") or "{}"
                
                try:
                    tool_args = json.loads(args_str)
                except json.JSONDecodeError:
                    tool_args = {}

                tool = self.registry.get(tool_name)
                if tool:
                    print(f"\n[Tool Call] {tool_name}({args_str})")
                    try:
                        result = await tool.execute(**tool_args)
                        print(f"[Tool Result] {result[:200]}{'...' if len(result) > 200 else ''}")
                    except Exception as e:
                        result = f"Error executing tool: {e}"
                        print(f"[Tool Error] {result}")
                else:
                    result = f"Unknown tool: {tool_name}"
                    print(f"[Tool Error] {result}")

                # Add tool result to conversation
                tool_msg = Message(
                    role="tool",
                    content=result,
                    tool_call_id=tool_call["id"],
                    name=tool_name,
                )
                conversation.append(tool_msg)

            # Continue loop to get final response (or more tool calls)
