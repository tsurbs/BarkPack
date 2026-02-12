"""Slack event handlers."""

import asyncio
import logging
import re
from dataclasses import dataclass, field
from typing import Any

from slack_sdk.web.async_client import AsyncWebClient

from bark.core.chatbot import ChatBot, Conversation
from bark.core.config import Settings, get_settings

from bark.core.formatting import SLACK_FORMAT_INSTRUCTIONS

logger = logging.getLogger(__name__)

# System prompt addendum for Slack-specific formatting
SLACK_SYSTEM_ADDENDUM = f"""You are communicating through Slack. {SLACK_FORMAT_INSTRUCTIONS}

Each message you receive is prefixed with "[From: username]" so you know who is speaking. You can address users by name when appropriate.

Keep responses concise.

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
    _conversation_locks: dict[str, asyncio.Lock] = field(default_factory=dict)
    _active_tools: dict[str, str] = field(default_factory=dict)  # conv key -> tool description

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
            self._process_and_respond(text, user, conversation, channel, thread_ts or ts, ts)
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
                self._process_and_respond(text, user, conversation, channel, thread_ts or ts, ts)
            )
            return

        # Handle replies in threads where Bark has participated
        if thread_ts and (channel, thread_ts) in self._bot_threads:
            logger.info(f"Handling thread reply from {user} in {channel}: {text}")
            conversation = self._get_or_create_conversation(channel, thread_ts)
            asyncio.create_task(
                self._process_and_respond(text, user, conversation, channel, thread_ts, ts)
            )

    async def _process_and_respond(
        self,
        text: str,
        user_id: str,
        conversation: Conversation,
        channel: str,
        thread_ts: str,
        message_ts: str = "",
    ) -> None:
        """Process a message and send a response.

        Uses a per-conversation lock to prevent concurrent mutation of the
        shared Conversation object.  If another request is already in-flight
        for this thread, we post an immediate status message so the user
        knows we're busy, then queue behind the lock.
        """
        if not self._chatbot or not self._client:
            logger.error("Handler not properly initialized")
            return

        conv_key = self._get_conversation_key(channel, thread_ts)

        # Get or create lock for this conversation
        if conv_key not in self._conversation_locks:
            self._conversation_locks[conv_key] = asyncio.Lock()
        lock = self._conversation_locks[conv_key]

        # If the lock is already held, post a status message and queue
        if lock.locked():
            active = self._active_tools.get(conv_key)
            if active:
                status = f"⏳ I'm currently working on *{active}* — I'll get to your message as soon as I'm done."
            else:
                status = "⏳ I'm still working on the previous request — I'll respond to your message shortly."
            try:
                await self._client.chat_postMessage(
                    channel=channel,
                    text=status,
                    thread_ts=thread_ts,
                )
            except Exception:
                pass  # Best-effort

        async with lock:
            await self._process_and_respond_locked(
                text, user_id, conversation, channel, thread_ts, message_ts, conv_key
            )

    async def _process_and_respond_locked(
        self,
        text: str,
        user_id: str,
        conversation: Conversation,
        channel: str,
        thread_ts: str,
        message_ts: str,
        conv_key: str,
    ) -> None:
        """Inner implementation of _process_and_respond, called under lock."""
        # Resolve user ID to display name
        user_name = await self._get_user_display_name(user_id)
        
        # Sanitize user text to prevent injection attacks where a user tries to
        # impersonate another by injecting fake "[From: X]" tags
        # Remove any bracketed prefixes that look like identity tags
        sanitized_text = re.sub(r'\[From:\s*[^\]]*\]\s*', '', text)
        
        # Prefix message with user identity so the bot knows who is speaking
        message_with_identity = f"[From: {user_name}] {sanitized_text}"

        # Track reactions we add so we can remove them after responding
        added_reactions: list[str] = []
        react_ts = message_ts or thread_ts  # The message to react to

        # Human-friendly tool name mapping for status messages
        _TOOL_DISPLAY_NAMES: dict[str, str] = {
            "code_agent": "running code",
            "writing_agent": "drafting text",
            "knowledge_agent": "researching",
            "firecrawl_scrape": "scraping a webpage",
            "firecrawl_crawl": "crawling a website",
            "gmail_search": "searching emails",
            "gmail_send": "sending an email",
            "gmail_read": "reading an email",
            "search_wiki": "searching the wiki",
            "search_notion": "searching Notion",
            "search_drive": "searching Drive",
            "sheets_read": "reading a spreadsheet",
            "docs_get": "reading a document",
            "calendar_list_events": "checking the calendar",
            "calendar_create_event": "creating a calendar event",
        }

        try:
            # Build a callback that reacts to the user's message
            async def _notify_tool_calls(
                tools: list[tuple[str, str]],
            ) -> None:
                """Add emoji reactions and update active-tool status."""
                # Map tool names to Slack emoji names
                _TOOL_EMOJI: dict[str, str] = {
                    "code_agent": "robot_face",
                    "volume_download": "inbox_tray",
                    "volume_download_drive": "inbox_tray",
                    "volume_list": "file_folder",
                    "volume_read": "eyes",
                    "firecrawl_scrape": "globe_with_meridians",
                    "firecrawl_crawl": "globe_with_meridians",
                    "gmail_search": "email",
                    "gmail_send": "outbox_tray",
                    "gmail_read": "email",
                    "calendar_list_events": "calendar",
                    "calendar_create_event": "calendar",
                    "refresh_context": "arrows_counterclockwise",
                    "search_wiki": "mag",
                    "search_notion": "mag",
                    "search_drive": "mag",
                    "sheets_read": "bar_chart",
                    "sheets_write": "bar_chart",
                    "docs_get": "page_facing_up",
                    "writing_agent": "pencil2",
                    "knowledge_agent": "brain",
                }

                # Update the active-tool description for status messages
                tool_names = [t_name for t_name, _ in tools]
                display_names = [
                    _TOOL_DISPLAY_NAMES.get(n, n) for n in tool_names
                ]
                self._active_tools[conv_key] = ", ".join(display_names)

                if not self._client or not react_ts:
                    return
                # Collect unique emojis for this batch of tool calls
                emojis_to_add: list[str] = []
                for t_name, _ in tools:
                    emoji = _TOOL_EMOJI.get(t_name)
                    if emoji and emoji not in added_reactions and emoji not in emojis_to_add:
                        emojis_to_add.append(emoji)
                for emoji in emojis_to_add:
                    try:
                        await self._client.reactions_add(
                            channel=channel,
                            timestamp=react_ts,
                            name=emoji,
                        )
                        added_reactions.append(emoji)
                    except Exception:
                        pass  # Best-effort (e.g. emoji already added)

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

            # Remove status reactions now that we've responded
            for emoji in added_reactions:
                try:
                    await self._client.reactions_remove(
                        channel=channel,
                        timestamp=react_ts,
                        name=emoji,
                    )
                except Exception:
                    pass  # Best-effort

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
        finally:
            # Clear active-tool status when done
            self._active_tools.pop(conv_key, None)
