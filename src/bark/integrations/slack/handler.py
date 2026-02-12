"""Slack event handlers."""

import asyncio
import logging
import re
from dataclasses import dataclass, field
from typing import Any

from slack_sdk.web.async_client import AsyncWebClient

from bark.core.chatbot import ChatBot, Conversation
from bark.core.config import Settings, get_settings

logger = logging.getLogger(__name__)

# System prompt addendum for Slack-specific formatting
SLACK_SYSTEM_ADDENDUM = """You are communicating through Slack. Use Slack's mrkdwn syntax for formatting:
- Bold: *text* (not **text**)
- Italic: _text_ (not *text*)
- Strikethrough: ~text~
- Code: `code` or ```code block```
- Links: <URL|text>
- Blockquotes: > text
- Bullet lists: - item or • item

Each message you receive is prefixed with "[From: username]" so you know who is speaking. You can address users by name when appropriate.

Keep responses concise. Do not use standard markdown syntax.

IMPORTANT: When you want to separate your response into multiple distinct messages, use double newlines (blank lines) between sections. Each section separated by blank lines will be sent as a separate Slack message."""


@dataclass
class SlackEventHandler:
    """Handles Slack events and routes them to the chatbot."""

    settings: Settings = field(default_factory=get_settings)
    _client: AsyncWebClient | None = None
    _chatbot: ChatBot | None = None
    _conversations: dict[str, Conversation] = field(default_factory=dict)
    _processed_events: set[str] = field(default_factory=set)
    _bot_threads: set[tuple[str, str]] = field(default_factory=set)
    _user_names: dict[str, str] = field(default_factory=dict)  # Cache user ID -> display name

    async def __aenter__(self) -> "SlackEventHandler":
        """Enter async context."""
        self._client = AsyncWebClient(token=self.settings.slack_bot_token)
        self._chatbot = ChatBot(settings=self.settings)
        await self._chatbot.__aenter__()
        return self

    async def __aexit__(self, *args: Any) -> None:
        """Exit async context."""
        if self._chatbot:
            await self._chatbot.__aexit__(*args)

    async def _get_user_display_name(self, user_id: str) -> str:
        """Resolve a Slack user ID to their display name.
        
        Args:
            user_id: The Slack user ID (e.g., U123456)
            
        Returns:
            The user's display name, or the user ID if lookup fails
        """
        if not user_id:
            return "Unknown"
        
        # Check cache first
        if user_id in self._user_names:
            return self._user_names[user_id]
        
        if not self._client:
            return user_id
        
        try:
            result = await self._client.users_info(user=user_id)
            user = result.get("user", {})
            # Prefer display_name, fall back to real_name, then name
            display_name = (
                user.get("profile", {}).get("display_name")
                or user.get("real_name")
                or user.get("name")
                or user_id
            )
            self._user_names[user_id] = display_name
            return display_name
        except Exception as e:
            logger.warning(f"Failed to resolve user {user_id}: {e}")
            return user_id

    def _get_conversation_key(self, channel: str, thread_ts: str | None) -> str:
        """Get a unique key for a conversation thread."""
        if thread_ts:
            return f"{channel}:{thread_ts}"
        return channel

    def _get_or_create_conversation(
        self, channel: str, thread_ts: str | None
    ) -> Conversation:
        """Get or create a conversation for a channel/thread."""
        key = self._get_conversation_key(channel, thread_ts)

        if key not in self._conversations:
            self._conversations[key] = self._chatbot.create_conversation(
                system_prompt_addendum=SLACK_SYSTEM_ADDENDUM
            )

        return self._conversations[key]

    async def handle_event(self, event: dict[str, Any]) -> dict[str, Any] | None:
        """Handle a Slack event.

        Args:
            event: The event payload from Slack

        Returns:
            Response to send back to Slack (if any)
        """
        event_type = event.get("type")

        if event_type == "url_verification":
            # Respond to Slack's URL verification challenge
            return {"challenge": event.get("challenge")}

        if event_type == "event_callback":
            inner_event = event.get("event", {})
            await self._handle_inner_event(inner_event, event.get("event_id"))

        return None

    async def _handle_inner_event(
        self, event: dict[str, Any], event_id: str | None
    ) -> None:
        """Handle the inner event from an event_callback."""
        # Deduplicate events
        if event_id and event_id in self._processed_events:
            logger.debug(f"Skipping duplicate event: {event_id}")
            return
        if event_id:
            self._processed_events.add(event_id)
            # Clean up old events (keep last 1000)
            if len(self._processed_events) > 1000:
                self._processed_events = set(list(self._processed_events)[-500:])

        event_type = event.get("type")

        if event_type == "app_mention":
            await self._handle_mention(event)
        elif event_type == "message":
            await self._handle_message(event)

    async def _handle_mention(self, event: dict[str, Any]) -> None:
        """Handle an app mention event."""
        # Get message details
        channel = event.get("channel", "")
        user = event.get("user", "")
        text = event.get("text", "")
        thread_ts = event.get("thread_ts") or event.get("ts")
        ts = event.get("ts", "")

        # Remove the bot mention from the text
        # Mentions look like <@U123456>
        text = re.sub(r"<@[A-Z0-9]+>\s*", "", text).strip()

        if not text:
            text = "Hello!"

        logger.info(f"Handling mention from {user} in {channel}: {text}")

        # Get or create conversation for this thread
        conversation = self._get_or_create_conversation(channel, thread_ts)

        # Process in background to respond quickly to Slack
        asyncio.create_task(
            self._process_and_respond(text, user, conversation, channel, thread_ts or ts)
        )

    async def _handle_message(self, event: dict[str, Any]) -> None:
        """Handle a direct message or thread reply event."""
        # Ignore bot messages to prevent loops
        if event.get("bot_id") or event.get("subtype") == "bot_message":
            return

        channel = event.get("channel", "")
        user = event.get("user", "")
        text = event.get("text", "")
        thread_ts = event.get("thread_ts")
        ts = event.get("ts", "")
        channel_type = event.get("channel_type")

        if not text:
            return

        # Handle DMs
        if channel_type == "im":
            logger.info(f"Handling DM from {user}: {text}")
            conversation = self._get_or_create_conversation(channel, thread_ts)
            asyncio.create_task(
                self._process_and_respond(text, user, conversation, channel, thread_ts or ts)
            )
            return

        # Handle replies in threads where Bark has participated
        if thread_ts and (channel, thread_ts) in self._bot_threads:
            logger.info(f"Handling thread reply from {user} in {channel}: {text}")
            conversation = self._get_or_create_conversation(channel, thread_ts)
            asyncio.create_task(
                self._process_and_respond(text, user, conversation, channel, thread_ts)
            )

    async def _process_and_respond(
        self,
        text: str,
        user_id: str,
        conversation: Conversation,
        channel: str,
        thread_ts: str,
    ) -> None:
        """Process a message and send a response."""
        if not self._chatbot or not self._client:
            logger.error("Handler not properly initialized")
            return

        # Resolve user ID to display name
        user_name = await self._get_user_display_name(user_id)
        
        # Sanitize user text to prevent injection attacks where a user tries to
        # impersonate another by injecting fake "[From: X]" tags
        # Remove any bracketed prefixes that look like identity tags
        sanitized_text = re.sub(r'\[From:\s*[^\]]*\]\s*', '', text)
        
        # Prefix message with user identity so the bot knows who is speaking
        message_with_identity = f"[From: {user_name}] {sanitized_text}"

        try:
            # Build a callback that posts tool status to Slack
            async def _notify_tool_calls(
                tools: list[tuple[str, str]],
            ) -> None:
                """Post a status message when bark starts running tools."""
                # Human-friendly names for tool categories
                _TOOL_DESCRIPTIONS: dict[str, str] = {
                    "code_agent": "🤖 Launching coding subagent…",
                    "volume_download": "📥 Downloading file…",
                    "volume_download_drive": "📥 Downloading from Google Drive…",
                    "firecrawl_scrape": "🌐 Scraping webpage…",
                    "firecrawl_crawl": "🌐 Crawling website…",
                    "gmail_search": "📧 Searching emails…",
                    "gmail_send": "📧 Sending email…",
                    "calendar_create_event": "📅 Creating calendar event…",
                    "refresh_context": "🔄 Refreshing wiki context…",
                }
                # Only post for tools that tend to be slow
                status_parts: list[str] = []
                for t_name, _ in tools:
                    if t_name in _TOOL_DESCRIPTIONS:
                        status_parts.append(_TOOL_DESCRIPTIONS[t_name])
                    elif t_name == "shell_exec":
                        status_parts.append("⚙️ Running shell command…")
                if status_parts and self._client:
                    status_msg = "\n".join(status_parts)
                    try:
                        await self._client.chat_postMessage(
                            channel=channel,
                            text=status_msg,
                            thread_ts=thread_ts,
                        )
                    except Exception:
                        pass  # Best-effort

            # Get response from chatbot
            response = await self._chatbot.chat(
                message_with_identity,
                conversation,
                on_tool_call=_notify_tool_calls,
            )

            # Check if bot decided not to reply
            if response.strip() == "__NO_REPLY__":
                logger.info("Bot chose not to reply")
                return

            # Split on unescaped double newlines (paragraph breaks)
            # Each paragraph becomes a separate Slack message
            messages = re.split(r'(?<!\\)\n\n+', response)

            for msg in messages:
                msg = msg.strip()
                if msg and msg != "__NO_REPLY__":
                    # Unescape any escaped newlines
                    msg = msg.replace('\\n', '\n')
                    await self._client.chat_postMessage(
                        channel=channel,
                        text=msg,
                        thread_ts=thread_ts,
                    )

            # Track this thread so we respond to follow-up messages
            self._bot_threads.add((channel, thread_ts))
            # Clean up old threads (keep last 500)
            if len(self._bot_threads) > 500:
                self._bot_threads = set(list(self._bot_threads)[-250:])

        except Exception as e:
            logger.exception(f"Error processing message: {e}")
            try:
                await self._client.chat_postMessage(
                    channel=channel,
                    text="Sorry, I encountered an error processing your message. Please try again.",
                    thread_ts=thread_ts,
                )
            except Exception:
                logger.exception("Failed to send error message")
