"""Background worker that periodically polls Gmail for new emails.

Runs as an asyncio task inside the FastAPI lifespan, checking for
unread messages sent to the configured target address at a regular
interval.
"""

import asyncio
import logging
from typing import Any

from bark.core.config import Settings, get_settings
from bark.interfaces.email.handler import EmailHandler

logger = logging.getLogger(__name__)


class EmailWorker:
    """Periodically polls Gmail for unread emails and processes them.

    Usage::

        worker = EmailWorker(settings=settings)
        await worker.start()   # launches background task
        ...
        await worker.stop()    # graceful shutdown
    """

    def __init__(
        self,
        settings: Settings | None = None,
        poll_interval: int | None = None,
        target_address: str | None = None,
    ) -> None:
        self._settings = settings or get_settings()
        self._poll_interval = (
            poll_interval
            if poll_interval is not None
            else self._settings.email_poll_interval
        )
        self._target_address = target_address or self._settings.email_target_address
        self._handler: EmailHandler | None = None
        self._task: asyncio.Task[Any] | None = None
        self._running = False

    async def start(self) -> None:
        """Initialise the handler and launch the polling loop."""
        if self._running:
            logger.warning("EmailWorker is already running")
            return

        self._handler = EmailHandler(settings=self._settings)
        await self._handler.__aenter__()
        self._running = True
        self._task = asyncio.create_task(self._poll_loop(), name="email-worker")
        logger.info(
            "EmailWorker started — polling %s every %ds",
            self._target_address,
            self._poll_interval,
        )

    async def stop(self) -> None:
        """Stop the polling loop and clean up resources."""
        self._running = False
        if self._task:
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass
            self._task = None

        if self._handler:
            await self._handler.__aexit__(None, None, None)
            self._handler = None

        logger.info("EmailWorker stopped")

    # ------------------------------------------------------------------
    # Internal polling loop
    # ------------------------------------------------------------------

    async def _poll_loop(self) -> None:
        """Main loop: fetch → process → sleep → repeat."""
        # Brief startup delay so other services can initialise first
        await asyncio.sleep(5)

        while self._running:
            try:
                await self._poll_once()
            except asyncio.CancelledError:
                raise
            except Exception:
                logger.exception("Error during email poll cycle")

            # Sleep until the next cycle (interruptible via cancellation)
            try:
                await asyncio.sleep(self._poll_interval)
            except asyncio.CancelledError:
                raise

    async def _poll_once(self) -> None:
        """Run a single poll-and-process cycle."""
        assert self._handler is not None

        emails = await self._handler.fetch_unread_emails(self._target_address)
        if not emails:
            return

        logger.info("Found %d new email(s) to process", len(emails))

        for email in emails:
            logger.info(
                "Processing email %s from %s — \"%s\"",
                email.message_id,
                email.sender_email,
                email.subject,
            )
            try:
                success = await self._handler.process_email(email)
                if success:
                    # Mark as read ONLY after successful response
                    await self._handler.mark_as_read(email.message_id)
                    logger.info("Successfully processed email %s", email.message_id)
                else:
                    logger.warning(
                        "Failed to process email %s — will retry next cycle",
                        email.message_id,
                    )
            except Exception:
                logger.exception("Unexpected error processing email %s", email.message_id)

        # Periodic housekeeping
        self._handler.cleanup_old_conversations()
