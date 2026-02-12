"""Email processing handler for Bark.

Fetches unread emails sent to the configured address, generates AI
responses using the same ChatBot pipeline as Slack, and sends replies
while maintaining thread context.
"""

import asyncio
import logging
from dataclasses import dataclass, field
from typing import Any

from bark.core.chatbot import ChatBot, Conversation
from bark.core.config import Settings, get_settings
from bark.core.formatting import GMAIL_FORMAT_INSTRUCTIONS
from bark.interfaces.email.utils import (
    build_reply_message,
    extract_body_text,
    extract_html_body,
    get_header,
    parse_email_address,
    parse_sender_name,
    quote_original_message,
    quote_original_message_html,
)

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# System prompt addendum for email-specific behaviour
# ---------------------------------------------------------------------------

EMAIL_SYSTEM_ADDENDUM = f"""You are communicating via email. Adopt a professional yet approachable tone.

{GMAIL_FORMAT_INSTRUCTIONS}

Email etiquette guidelines:
- Open with an appropriate greeting (e.g. "Hi <name>," or "Hello,")
- Close with a brief sign-off (e.g. "Best," or "Thanks,") — your signature block is added automatically, do NOT add one yourself.
- Be thorough — email readers expect more complete answers than chat users.
- Use proper paragraphs and formatting for readability.
- When replying, address the sender's questions or concerns directly.
- Do NOT include "[From: ...]" tags — those are for Slack only.
- Do NOT use Slack mrkdwn syntax — use HTML as described above.

Each incoming email is prefixed with "[From: sender name <email>]" and "[Subject: ...]" so you know the context. Address the sender by name when appropriate."""


# ---------------------------------------------------------------------------
# Data container for a parsed inbound email
# ---------------------------------------------------------------------------

@dataclass
class InboundEmail:
    """Parsed representation of an inbound Gmail message."""

    message_id: str
    thread_id: str
    sender_raw: str  # Full "Name <email>" string
    sender_email: str
    sender_name: str
    to: str
    subject: str
    date: str
    body_text: str
    body_html: str
    gmail_message_id_header: str  # RFC 2822 Message-ID header
    references_header: str  # Existing References header for threading


# ---------------------------------------------------------------------------
# EmailHandler
# ---------------------------------------------------------------------------

@dataclass
class EmailHandler:
    """Processes inbound emails and generates AI-powered replies.

    Manages per-thread conversations so follow-up emails in the same
    Gmail thread maintain context across multiple exchanges.
    """

    settings: Settings = field(default_factory=get_settings)
    _chatbot: ChatBot | None = None
    _conversations: dict[str, Conversation] = field(default_factory=dict)
    _processed_ids: set[str] = field(default_factory=set)
    _own_email: str | None = None

    async def __aenter__(self) -> "EmailHandler":
        """Enter async context — initialise ChatBot."""
        self._chatbot = ChatBot(settings=self.settings)
        await self._chatbot.__aenter__()

        # Resolve our own email address so we can filter self-sent messages
        try:
            self._own_email = await self._resolve_own_email()
            logger.info("Resolved own email address: %s", self._own_email)
        except Exception:
            logger.warning(
                "Could not resolve own email address — "
                "will rely on query-level filtering only"
            )

        return self

    async def __aexit__(self, *args: Any) -> None:
        """Exit async context — clean up ChatBot."""
        if self._chatbot:
            await self._chatbot.__aexit__(*args)

    # ------------------------------------------------------------------
    # Gmail API helpers (run in thread to avoid blocking the event loop)
    # ------------------------------------------------------------------

    def _get_gmail_service(self) -> Any:
        """Return the Gmail API service object."""
        from bark.context.google_auth import get_google_auth
        return get_google_auth().gmail

    async def _resolve_own_email(self) -> str:
        """Fetch the authenticated Gmail user's email address."""
        svc = self._get_gmail_service()
        from bark.core.tools import _sync_tool_lock

        def _get_profile() -> str:
            with _sync_tool_lock:
                profile = svc.users().getProfile(userId="me").execute()
                return profile.get("emailAddress", "")

        return await asyncio.to_thread(_get_profile)

    def _is_self_sent(self, email: "InboundEmail") -> bool:
        """Check if an email was sent by us (to prevent reply loops)."""
        sender = email.sender_email.lower()

        # Check against resolved own email
        if self._own_email and sender == self._own_email.lower():
            return True

        # Check against the configured target address (Bark's address)
        target = self.settings.email_target_address.lower()
        if sender == target:
            return True

        # Also match the base address without the +bark alias
        # e.g. ops+bark@scottylabs.org -> ops@scottylabs.org
        base_target = target.replace("+bark", "")
        if sender == base_target:
            return True

        return False

    async def fetch_unread_emails(self, target_address: str) -> list[InboundEmail]:
        """Fetch unread emails addressed to *target_address*.

        Uses the Gmail API search: ``to:<target_address> is:unread -from:me``
        The ``-from:me`` filter prevents processing our own sent replies.
        """
        svc = self._get_gmail_service()
        # Exclude emails from ourselves to prevent reply loops
        query = f"to:{target_address} is:unread -from:me"

        # Run blocking Google API call in a thread
        from bark.core.tools import _sync_tool_lock

        def _search() -> list[dict]:
            with _sync_tool_lock:
                results = (
                    svc.users()
                    .messages()
                    .list(userId="me", q=query, maxResults=10)
                    .execute()
                )
                return results.get("messages", [])

        try:
            stubs = await asyncio.to_thread(_search)
        except Exception:
            logger.exception("Gmail API search failed for query: %s", query)
            return []

        if not stubs:
            return []

        emails: list[InboundEmail] = []
        for stub in stubs:
            msg_id = stub["id"]

            # Skip already-processed messages
            if msg_id in self._processed_ids:
                continue

            try:
                email = await self._fetch_and_parse(svc, msg_id)
                if email is None:
                    continue

                # Double-check: skip self-sent messages that slipped through
                if self._is_self_sent(email):
                    logger.debug(
                        "Skipping self-sent email %s from %s",
                        msg_id, email.sender_email,
                    )
                    # Mark as processed so we don't recheck every cycle
                    self._processed_ids.add(msg_id)
                    continue

                emails.append(email)
            except Exception:
                logger.exception("Failed to fetch/parse email %s", msg_id)

        return emails

    async def _fetch_and_parse(self, svc: Any, msg_id: str) -> InboundEmail | None:
        """Fetch a single message and parse it into an InboundEmail."""
        from bark.core.tools import _sync_tool_lock

        def _get() -> dict:
            with _sync_tool_lock:
                return (
                    svc.users()
                    .messages()
                    .get(userId="me", id=msg_id, format="full")
                    .execute()
                )

        msg = await asyncio.to_thread(_get)
        headers = msg.get("payload", {}).get("headers", [])
        payload = msg.get("payload", {})

        sender_raw = get_header(headers, "From")
        subject = get_header(headers, "Subject")
        date = get_header(headers, "Date")
        to = get_header(headers, "To")
        message_id_header = get_header(headers, "Message-ID") or get_header(headers, "Message-Id")
        references_header = get_header(headers, "References")

        body_text = extract_body_text(payload)
        body_html = extract_html_body(payload)

        if not body_text and not body_html:
            logger.warning("Email %s has no extractable body — skipping", msg_id)
            return None

        return InboundEmail(
            message_id=msg_id,
            thread_id=msg.get("threadId", msg_id),
            sender_raw=sender_raw,
            sender_email=parse_email_address(sender_raw),
            sender_name=parse_sender_name(sender_raw),
            to=to,
            subject=subject,
            date=date,
            body_text=body_text if body_text else "",
            body_html=body_html,
            gmail_message_id_header=message_id_header,
            references_header=references_header,
        )

    # ------------------------------------------------------------------
    # Response generation
    # ------------------------------------------------------------------

    def _get_or_create_conversation(self, thread_id: str) -> Conversation:
        """Get or create a Conversation for a Gmail thread."""
        if thread_id not in self._conversations:
            assert self._chatbot is not None
            self._conversations[thread_id] = self._chatbot.create_conversation(
                system_prompt_addendum=EMAIL_SYSTEM_ADDENDUM,
            )
        return self._conversations[thread_id]

    async def process_email(self, email: InboundEmail) -> bool:
        """Generate an AI response and send it as a reply.

        Returns True if the reply was sent successfully, False otherwise.
        The caller should only mark the email as read when this returns True.
        """
        if not self._chatbot:
            logger.error("EmailHandler not initialised — call __aenter__ first")
            return False

        conversation = self._get_or_create_conversation(email.thread_id)

        # Build the user message with sender identity
        user_message = (
            f"[From: {email.sender_name} <{email.sender_email}>]\n"
            f"[Subject: {email.subject}]\n\n"
            f"{email.body_text}"
        )

        try:
            response_html = await self._chatbot.chat(user_message, conversation)
        except Exception:
            logger.exception("ChatBot error while processing email %s", email.message_id)
            return False

        if not response_html or response_html.strip() == "__NO_REPLY__":
            logger.info("Bot chose not to reply to email %s", email.message_id)
            # Still mark as processed so we don't retry
            self._processed_ids.add(email.message_id)
            return True

        # Build plain-text version by stripping HTML
        from bark.interfaces.email.utils import extract_text_from_html
        response_plain = extract_text_from_html(response_html)
        if not response_plain:
            response_plain = response_html  # Fallback: use as-is

        # Construct quoted original
        quoted_plain = quote_original_message(
            email.sender_raw, email.date, email.body_text,
        )
        quoted_html = quote_original_message_html(
            email.sender_raw, email.date, email.body_html or None, email.body_text,
        )

        # Build the reply subject line
        reply_subject = email.subject
        if not reply_subject.lower().startswith("re:"):
            reply_subject = f"Re: {reply_subject}"

        # Determine the From address for the reply
        from_address = self._own_email or self.settings.email_target_address

        # Build MIME message
        reply_body = build_reply_message(
            from_addr=from_address,
            to=email.sender_email,
            subject=reply_subject,
            body_html=response_html + quoted_html,
            body_plain=response_plain + quoted_plain,
            original_message_id=email.gmail_message_id_header,
            references=email.references_header,
            thread_id=email.thread_id,
        )

        # Send via Gmail API
        try:
            success = await self._send_reply(reply_body)
            if success:
                self._processed_ids.add(email.message_id)
                return True
            return False
        except Exception:
            logger.exception("Failed to send reply for email %s", email.message_id)
            return False

    async def _send_reply(self, message_body: dict) -> bool:
        """Send an email reply via the Gmail API."""
        svc = self._get_gmail_service()
        from bark.core.tools import _sync_tool_lock

        def _send() -> dict:
            with _sync_tool_lock:
                return (
                    svc.users()
                    .messages()
                    .send(userId="me", body=message_body)
                    .execute()
                )

        result = await asyncio.to_thread(_send)
        sent_id = result.get("id", "?")
        logger.info("Reply sent — Gmail message ID: %s", sent_id)
        return True

    async def mark_as_read(self, message_id: str) -> None:
        """Mark a Gmail message as read by removing the UNREAD label."""
        svc = self._get_gmail_service()
        from bark.core.tools import _sync_tool_lock

        def _modify() -> None:
            with _sync_tool_lock:
                svc.users().messages().modify(
                    userId="me",
                    id=message_id,
                    body={"removeLabelIds": ["UNREAD"]},
                ).execute()

        await asyncio.to_thread(_modify)
        logger.info("Marked email %s as read", message_id)

    # ------------------------------------------------------------------
    # Housekeeping
    # ------------------------------------------------------------------

    def cleanup_old_conversations(self, max_threads: int = 200) -> None:
        """Evict oldest conversations to prevent unbounded memory growth."""
        if len(self._conversations) > max_threads:
            # Keep the most recent half
            keep = max_threads // 2
            keys = list(self._conversations.keys())
            for key in keys[:-keep]:
                del self._conversations[key]

        # Also trim the processed-IDs set
        if len(self._processed_ids) > 5000:
            self._processed_ids = set(list(self._processed_ids)[-2500:])
