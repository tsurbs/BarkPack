"""Nvidia API client for chat completions with tool support."""

import asyncio
import json
import time
from dataclasses import dataclass, field
from typing import Any, AsyncGenerator, Callable, Awaitable

# Type alias for the tool-call notification callback.
# Called with a list of (tool_name, arguments_json) tuples before execution.
ToolCallCallback = Callable[[list[tuple[str, str]]], Awaitable[None]]

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
class NvidiaClient:
    """Async client for Nvidia API."""

    settings: Settings = field(default_factory=get_settings)
    registry: ToolRegistry = field(default_factory=get_registry)
    _client: httpx.AsyncClient | None = None

    async def __aenter__(self) -> "NvidiaClient":
        """Enter async context."""
        self._client = httpx.AsyncClient(
            base_url=self.settings.nvidia_base_url,
            headers={
                "Authorization": f"Bearer {self.settings.nvidia_api_key}",
                "Content-Type": "application/json",
                "Accept": "application/json",
            },
            timeout=180.0,
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
        on_tool_call: ToolCallCallback | None = None,
    ) -> Message:
        """Send a chat completion request and handle tool calls.

        This method will automatically execute tool calls and continue
        the conversation until a final response is received.
        """
        if not self._client:
            raise RuntimeError("Client not initialized. Use 'async with' context.")

        model = model or self.settings.nvidia_model
        print("Using model: ", model)
        conversation = list(messages)  # Copy to avoid mutating input

        while True:
            # Build request payload
            payload: dict[str, Any] = {
                "model": model,
                "messages": [m.to_dict() for m in conversation],
                "max_tokens": 16384,
                "temperature": 1.00,
                "top_p": 1.00,
                "chat_template_kwargs": {"thinking": True},
            }

            # Add tools if available
            tools = self.registry.to_openai_schema()
            if tools:
                payload["tools"] = tools
                payload["tool_choice"] = "auto"

            # Make request
            start_time = time.time()
            response = await self._client.post("/chat/completions", json=payload)
            duration = time.time() - start_time
            print(f"[Debug] API request took {duration:.2f}s")
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

            # Notify caller about tool calls (for status messages)
            if on_tool_call:
                tool_info = [
                    (tc["function"]["name"], tc["function"].get("arguments", "{}") or "{}")
                    for tc in message["tool_calls"]
                ]
                try:
                    await on_tool_call(tool_info)
                except Exception:
                    pass  # Don't let callback errors break tool execution

            # Execute all tool calls in parallel
            async def _run_tool(tc: dict[str, Any]) -> Message:
                t_name = tc["function"]["name"]
                a_str = tc["function"].get("arguments", "{}") or "{}"
                t_args = json.loads(a_str)
                t = self.registry.get(t_name)
                if t:
                    print(f"\n[Tool Call] {t_name}({a_str})")
                    t_start = time.time()
                    try:
                        res = await t.execute(**t_args)
                        dur = time.time() - t_start
                        print(f"[Tool Result] {res[:200]}{'...' if len(res) > 200 else ''} ({dur:.2f}s)")
                    except Exception as e:
                        dur = time.time() - t_start
                        res = f"Error executing tool: {e}"
                        print(f"[Tool Error] {res} ({dur:.2f}s)")
                else:
                    res = f"Unknown tool: {t_name}"
                    print(f"[Tool Error] {res}")
                return Message(role="tool", content=res, tool_call_id=tc["id"], name=t_name)

            tool_results = await asyncio.gather(
                *[_run_tool(tc) for tc in message["tool_calls"]]
            )
            conversation.extend(tool_results)

            # Continue loop to get final response

    async def stream_chat(
        self,
        messages: list[Message],
        model: str | None = None,
        on_tool_call: ToolCallCallback | None = None,
    ) -> AsyncGenerator[str, None]:
        """Send a chat completion request with streaming and handle tool calls.

        This method will automatically execute tool calls and continue
        the conversation until a final response is received.
        """
        if not self._client:
            raise RuntimeError("Client not initialized. Use 'async with' context.")

        model = model or self.settings.nvidia_model
        print("Using model: ", model)
        conversation = list(messages)  # Copy to avoid mutating input

        while True:
            # Build request payload
            payload: dict[str, Any] = {
                "model": model,
                "messages": [m.to_dict() for m in conversation],
                "stream": True,
                "max_tokens": 16384,
                "temperature": 1.00,
                "top_p": 1.00,
                "chat_template_kwargs": {"thinking": True},
            }

            # Add tools if available
            tools = self.registry.to_openai_schema()
            if tools:
                payload["tools"] = tools
                payload["tool_choice"] = "auto"

            # Make request
            full_content = ""
            tool_calls: list[dict[str, Any]] = []

            start_time = time.time()
            first_token_time = None
            
            # Update headers for streaming
            headers = self._client.headers.copy()
            headers["Accept"] = "text/event-stream"

            async with self._client.stream("POST", "/chat/completions", json=payload, headers=headers) as response:
                duration = time.time() - start_time
                print(f"[Debug] Stream connection took {duration:.2f}s")
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
                        if first_token_time is None:
                            first_token_time = time.time()
                            print(f"[Debug] Time to first token: {first_token_time - start_time:.2f}s")
                        
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

            # Notify caller about tool calls (for status messages)
            if on_tool_call:
                tool_info = [
                    (tc["function"]["name"], tc["function"].get("arguments", "{}") or "{}")
                    for tc in tool_calls
                ]
                try:
                    await on_tool_call(tool_info)
                except Exception:
                    pass

            # Execute all tool calls in parallel
            async def _run_tool(tc: dict[str, Any]) -> Message:
                t_name = tc["function"]["name"]
                a_str = tc["function"].get("arguments", "{}") or "{}"
                try:
                    t_args = json.loads(a_str)
                except json.JSONDecodeError:
                    t_args = {}
                t = self.registry.get(t_name)
                if t:
                    print(f"\n[Tool Call] {t_name}({a_str})")
                    t_start = time.time()
                    try:
                        res = await t.execute(**t_args)
                        dur = time.time() - t_start
                        print(f"[Tool Result] {res[:200]}{'...' if len(res) > 200 else ''} ({dur:.2f}s)")
                    except Exception as e:
                        dur = time.time() - t_start
                        res = f"Error executing tool: {e}"
                        print(f"[Tool Error] {res} ({dur:.2f}s)")
                else:
                    res = f"Unknown tool: {t_name}"
                    print(f"[Tool Error] {res}")
                return Message(role="tool", content=res, tool_call_id=tc["id"], name=t_name)

            tool_results = await asyncio.gather(
                *[_run_tool(tc) for tc in tool_calls]
            )
            conversation.extend(tool_results)

            # Continue loop to get final response (or more tool calls)
