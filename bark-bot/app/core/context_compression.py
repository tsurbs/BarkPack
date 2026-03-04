"""
Context Compression — automatically compresses conversation history when
it exceeds a configurable token threshold.

When triggered, older messages are summarised via a cheap LLM call and
the full history is replaced with [system_prompt, summary, ...recent_messages].
Summaries are cached in the `context_summaries` DB table so repeated
compressions for the same conversation reuse existing work.
"""

import tiktoken
from typing import Optional
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.core.llm import generate_response
from app.db.models import ContextSummary

# Number of recent messages to protect from compression
PROTECTED_RECENT_MESSAGES = 10

# tiktoken encoder — cl100k_base works well as a general approximation
_encoder = tiktoken.get_encoding("cl100k_base")


def count_message_tokens(messages: list[dict]) -> int:
    """Return an approximate token count for a list of chat messages."""
    total = 0
    for msg in messages:
        # ~4 tokens of overhead per message (role, separators, etc.)
        total += 4
        total += len(_encoder.encode(msg.get("content") or ""))
        if msg.get("tool_calls"):
            # Rough estimate for serialised tool-call JSON
            import json
            total += len(_encoder.encode(json.dumps(msg["tool_calls"])))
    return total


async def _get_cached_summary(
    db: AsyncSession, conversation_id: str, message_count: int
) -> Optional[str]:
    """Return a cached summary if one exists for this conversation + message count."""
    if not db or not conversation_id:
        return None
    result = await db.execute(
        select(ContextSummary)
        .where(ContextSummary.conversation_id == conversation_id)
        .where(ContextSummary.messages_summarized == str(message_count))
        .order_by(ContextSummary.created_at.desc())
        .limit(1)
    )
    row = result.scalar_one_or_none()
    return row.summary if row else None


async def _save_summary(
    db: AsyncSession, conversation_id: str, summary: str, message_count: int
) -> None:
    """Persist a new compression summary to the database."""
    if not db or not conversation_id:
        return
    entry = ContextSummary(
        conversation_id=conversation_id,
        summary=summary,
        messages_summarized=str(message_count),
    )
    db.add(entry)
    await db.commit()


async def compress_context(
    messages: list[dict],
    token_limit: int,
    summary_model: str = "openrouter/auto",
    db: AsyncSession = None,
    conversation_id: str = None,
) -> list[dict]:
    """
    Compress ``messages`` if they exceed ``token_limit`` tokens.

    Returns the (potentially compressed) message list.  If compression is
    not needed the original list is returned unchanged.
    """
    total_tokens = count_message_tokens(messages)
    if total_tokens <= token_limit:
        return messages

    print(
        f"[Context Compression] {total_tokens} tokens exceeds limit of "
        f"{token_limit}. Compressing…"
    )

    # --- Split into protected / compressible ---
    # Protected: system prompt (index 0) + last N messages
    system_prompt = messages[0] if messages and messages[0].get("role") == "system" else None
    start_idx = 1 if system_prompt else 0

    # Keep the most recent PROTECTED_RECENT_MESSAGES
    protect_count = min(PROTECTED_RECENT_MESSAGES, len(messages) - start_idx)
    split_point = len(messages) - protect_count

    compressible = messages[start_idx:split_point]
    protected_recent = messages[split_point:]

    if not compressible:
        # Nothing old enough to compress — return as-is
        return messages

    # --- Check DB cache ---
    cache_key = len(compressible)
    cached = await _get_cached_summary(db, conversation_id, cache_key)

    if cached:
        print("[Context Compression] Reusing cached summary from DB.")
        summary_text = cached
    else:
        # --- Generate summary via cheap model ---
        log_lines = []
        for msg in compressible:
            role = msg.get("role", "unknown")
            content = (msg.get("content") or "")[:2000]  # Truncate very long entries
            log_lines.append(f"{role}: {content}")
        log_block = "\n".join(log_lines)

        summarization_prompt = [
            {
                "role": "system",
                "content": (
                    "You are a concise summariser. Given a conversation log, "
                    "produce a dense, factual summary that preserves all key "
                    "information, decisions, tool results, and user preferences. "
                    "Omit filler and repetition. Output ONLY the summary."
                ),
            },
            {
                "role": "user",
                "content": f"Summarise this conversation history:\n\n{log_block}",
            },
        ]

        result = await generate_response(
            summarization_prompt, tools=None, model=summary_model
        )
        summary_text = result.get("content", "")

        if not summary_text:
            print("[Context Compression] Summary generation failed; skipping compression.")
            return messages

        # Persist to DB
        await _save_summary(db, conversation_id, summary_text, cache_key)
        print("[Context Compression] Summary generated and saved to DB.")

    # --- Reassemble ---
    compressed_msg = {
        "role": "system",
        "content": (
            f"[Compressed History — the following is an AI-generated summary of "
            f"{len(compressible)} earlier messages in this conversation]\n\n"
            f"{summary_text}"
        ),
    }

    result_messages = []
    if system_prompt:
        result_messages.append(system_prompt)
    result_messages.append(compressed_msg)
    result_messages.extend(protected_recent)

    new_tokens = count_message_tokens(result_messages)
    print(
        f"[Context Compression] Reduced from {total_tokens} to ~{new_tokens} tokens."
    )
    return result_messages
