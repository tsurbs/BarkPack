"""Specialist delegation tools for multi-model routing.

Provides `writing_agent` and `knowledge_agent` tools that delegate tasks
to specialized models via OpenRouter. The orchestrator (Kimi) calls these
tools when it decides a task is best handled by a specialist, passing along
the full conversation context so the specialist can produce a well-informed
response.
"""

import json
import logging
import time
from typing import Any

import httpx

from bark.core.config import get_settings
from bark.core.tools import tool

logger = logging.getLogger(__name__)

# Max seconds to wait for a specialist model response
SPECIALIST_TIMEOUT = 180


async def _run_specialist(
    task: str,
    context: str,
    model: str,
    system_prompt: str,
) -> str:
    """Run a specialist model with context and return its response.

    Args:
        task: The specific task for the specialist to complete.
        context: Conversation context / background info from the orchestrator.
        model: The OpenRouter model identifier to use.
        system_prompt: System prompt defining the specialist's role.

    Returns:
        The specialist model's text response.
    """
    settings = get_settings()

    # Build the user message with context + task
    parts: list[str] = []
    if context:
        parts.append(f"## Conversation Context\n\n{context}")
    parts.append(f"## Task\n\n{task}")
    user_content = "\n\n---\n\n".join(parts)

    messages: list[dict[str, Any]] = [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": user_content},
    ]

    payload = {
        "model": model,
        "messages": messages,
    }

    async with httpx.AsyncClient(
        base_url=settings.openrouter_base_url,
        headers={
            "Authorization": f"Bearer {settings.openrouter_api_key}",
            "Content-Type": "application/json",
        },
        timeout=SPECIALIST_TIMEOUT,
    ) as client:
        start = time.time()
        logger.info(f"[Specialist] Calling {model}")
        resp = await client.post("/chat/completions", json=payload)
        duration = time.time() - start
        logger.info(f"[Specialist] {model} responded in {duration:.2f}s")
        resp.raise_for_status()
        data = resp.json()

        return data["choices"][0]["message"].get("content", "(no content)")


# ---------------------------------------------------------------------------
# Writing Agent
# ---------------------------------------------------------------------------

WRITING_SYSTEM_PROMPT = """You are a specialist writing assistant. You excel at:
- Drafting clear, well-structured documents, emails, and messages
- Creative writing and copywriting
- Summarizing and rewriting content
- Adjusting tone and style to match the audience

You will receive conversation context and a specific writing task.
Use the context to understand what has been discussed and produce exactly
what is requested. Be thorough and produce polished, ready-to-use output."""


@tool(
    name="writing_agent",
    description=(
        "Delegate a writing task to a specialist writing model (Gemini 3 Flash). "
        "Use for drafting emails, documents, long-form text, creative writing, "
        "or any task where high-quality written output is the goal.\n\n"
        "IMPORTANT: Always provide conversation context so the specialist "
        "understands the full situation."
    ),
    parameters={
        "type": "object",
        "properties": {
            "task": {
                "type": "string",
                "description": (
                    "Clear, detailed description of what to write. "
                    "Include the desired format, tone, length, and audience."
                ),
            },
            "context": {
                "type": "string",
                "description": (
                    "Conversation context and background information. "
                    "Summarize the conversation so far and any relevant details "
                    "the writing specialist needs to know."
                ),
            },
        },
        "required": ["task"],
    },
)
async def writing_agent(task: str, context: str = "") -> str:
    """Delegate a writing task to the specialist writing model."""
    try:
        settings = get_settings()
        result = await _run_specialist(
            task=task,
            context=context,
            model=settings.writing_model,
            system_prompt=WRITING_SYSTEM_PROMPT,
        )
        return f"**Writing Specialist Result:**\n\n{result}"
    except httpx.HTTPStatusError as e:
        return f"❌ Writing agent API error: HTTP {e.response.status_code}"
    except Exception as e:
        logger.exception("Writing agent failed")
        return f"❌ Writing agent error: {e}"


# ---------------------------------------------------------------------------
# Knowledge Agent
# ---------------------------------------------------------------------------

KNOWLEDGE_SYSTEM_PROMPT = """You are a specialist knowledge assistant. You excel at:
- Deep, thorough answers to complex factual questions
- Research synthesis and analysis
- Technical explanations with nuance and accuracy
- Comparing and contrasting concepts in detail

You will receive conversation context and a specific knowledge question or task.
Use the context to understand what has been discussed and provide a comprehensive,
well-organized answer. Cite your reasoning and be precise."""


@tool(
    name="knowledge_agent",
    description=(
        "Delegate a deep knowledge or research question to a specialist "
        "knowledge model (Gemini 3 Pro). Use for complex factual questions, "
        "research synthesis, detailed technical explanations, or any task "
        "requiring deep general knowledge.\n\n"
        "IMPORTANT: Always provide conversation context so the specialist "
        "understands the full situation."
    ),
    parameters={
        "type": "object",
        "properties": {
            "task": {
                "type": "string",
                "description": (
                    "The knowledge question or research task. "
                    "Be specific about what information is needed "
                    "and the level of detail expected."
                ),
            },
            "context": {
                "type": "string",
                "description": (
                    "Conversation context and background information. "
                    "Summarize the conversation so far and any relevant details "
                    "the knowledge specialist needs to know."
                ),
            },
        },
        "required": ["task"],
    },
)
async def knowledge_agent(task: str, context: str = "") -> str:
    """Delegate a knowledge task to the specialist knowledge model."""
    try:
        settings = get_settings()
        result = await _run_specialist(
            task=task,
            context=context,
            model=settings.knowledge_model,
            system_prompt=KNOWLEDGE_SYSTEM_PROMPT,
        )
        return f"**Knowledge Specialist Result:**\n\n{result}"
    except httpx.HTTPStatusError as e:
        return f"❌ Knowledge agent API error: HTTP {e.response.status_code}"
    except Exception as e:
        logger.exception("Knowledge agent failed")
        return f"❌ Knowledge agent error: {e}"
