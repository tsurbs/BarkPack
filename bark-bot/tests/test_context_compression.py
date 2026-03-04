"""
Unit tests for app.core.context_compression
"""

import asyncio
import pytest
from unittest.mock import AsyncMock, patch, MagicMock

from app.core.context_compression import count_message_tokens, compress_context, PROTECTED_RECENT_MESSAGES


def test_count_message_tokens_basic():
    """Token count returns a positive integer for simple messages."""
    messages = [
        {"role": "system", "content": "You are a helpful assistant."},
        {"role": "user", "content": "Hello, how are you?"},
        {"role": "assistant", "content": "I'm doing well, thanks for asking!"},
    ]
    count = count_message_tokens(messages)
    assert isinstance(count, int)
    assert count > 0


def test_count_message_tokens_empty():
    """Empty message list returns 0."""
    assert count_message_tokens([]) == 0


def test_count_message_tokens_with_none_content():
    """Messages with None content don't crash."""
    messages = [{"role": "assistant", "content": None}]
    count = count_message_tokens(messages)
    assert isinstance(count, int)
    assert count >= 4  # At least the overhead tokens


@pytest.mark.asyncio
async def test_compress_context_under_limit():
    """Messages under the token limit are returned unchanged."""
    messages = [
        {"role": "system", "content": "System prompt"},
        {"role": "user", "content": "Hello"},
        {"role": "assistant", "content": "Hi there!"},
    ]
    result = await compress_context(messages, token_limit=100000)
    assert result is messages  # Same object, not a copy


@pytest.mark.asyncio
async def test_compress_context_over_limit():
    """When over the limit, older messages get compressed into a summary."""
    # Build a message list that is definitely over a small limit
    messages = [{"role": "system", "content": "System prompt"}]
    for i in range(30):
        messages.append({"role": "user", "content": f"Message number {i} " * 50})
        messages.append({"role": "assistant", "content": f"Reply number {i} " * 50})

    mock_response = {"content": "Summary of the conversation so far."}

    with patch("app.core.context_compression.generate_response", new_callable=AsyncMock, return_value=mock_response):
        with patch("app.core.context_compression._get_cached_summary", new_callable=AsyncMock, return_value=None):
            with patch("app.core.context_compression._save_summary", new_callable=AsyncMock):
                result = await compress_context(messages, token_limit=500)

    # Should have: system + compressed_summary + last N protected messages
    assert result[0]["role"] == "system"
    assert result[0]["content"] == "System prompt"
    assert result[1]["role"] == "system"
    assert "[Compressed History" in result[1]["content"]
    assert "Summary of the conversation" in result[1]["content"]
    # Recent messages preserved
    assert len(result) == 2 + PROTECTED_RECENT_MESSAGES


@pytest.mark.asyncio
async def test_compress_context_uses_cached_summary():
    """When a cached summary exists, the LLM is NOT called."""
    messages = [{"role": "system", "content": "System prompt"}]
    for i in range(30):
        messages.append({"role": "user", "content": f"Message {i} " * 50})
        messages.append({"role": "assistant", "content": f"Reply {i} " * 50})

    with patch("app.core.context_compression._get_cached_summary", new_callable=AsyncMock, return_value="Cached summary text"):
        with patch("app.core.context_compression.generate_response", new_callable=AsyncMock) as mock_llm:
            result = await compress_context(messages, token_limit=500, db=MagicMock(), conversation_id="test-conv")

    # LLM should NOT have been called
    mock_llm.assert_not_called()
    assert "[Compressed History" in result[1]["content"]
    assert "Cached summary text" in result[1]["content"]
