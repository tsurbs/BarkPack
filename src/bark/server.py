# Claude Code Server integration verified
"""FastAPI server for Bark integrations."""

import json
import logging
from contextlib import asynccontextmanager
from typing import Any

from fastapi import FastAPI, Request, Response
from fastapi.middleware.cors import CORSMiddleware

from bark.core.config import get_settings
from bark.dashboard_api import router as dashboard_router
from bark.integrations.slack.handler import SlackEventHandler
from bark.integrations.slack.verification import verify_slack_signature_from_body
from bark.interfaces.email.worker import EmailWorker

# Import tools to register them
import bark.tools  # noqa: F401

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)

# Global handler instances
slack_handler: SlackEventHandler | None = None
email_worker: EmailWorker | None = None


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan manager."""
    global slack_handler, email_worker

    settings = get_settings()

    # Initialize Slack handler if configured
    if settings.slack_bot_token and settings.slack_signing_secret:
        slack_handler = SlackEventHandler(settings=settings)
        await slack_handler.__aenter__()
        logger.info("Slack integration initialized")
    else:
        logger.warning("Slack integration not configured (missing credentials)")

    # Initialize Email worker if enabled and Google credentials are available.
    # Note: google_drive_credentials_file defaults to "credentials.json" which
    # may not actually exist, so we check google_drive_credentials_json (the
    # primary production path) or verify the file actually exists on disk.
    import os
    has_google_creds = bool(settings.google_drive_credentials_json) or (
        settings.google_drive_credentials_file
        and os.path.exists(settings.google_drive_credentials_file)
    )
    if settings.email_enabled and has_google_creds:
        try:
            email_worker = EmailWorker(settings=settings)
            await email_worker.start()
            logger.info(
                "Email interface initialized — polling %s every %ds",
                settings.email_target_address,
                settings.email_poll_interval,
            )
        except Exception:
            logger.exception("Failed to start email worker")
            email_worker = None
    else:
        if not settings.email_enabled:
            logger.info("Email interface disabled (EMAIL_ENABLED=false)")
        else:
            logger.info(
                "Email interface not started — no Google credentials found "
                "(set GOOGLE_DRIVE_CREDENTIALS_JSON or provide a credentials file)"
            )

    yield

    # Cleanup
    if email_worker:
        await email_worker.stop()
    if slack_handler:
        await slack_handler.__aexit__(None, None, None)


app = FastAPI(
    title="Bark",
    description="A chatbot for ScottyLabs",
    version="0.1.0",
    lifespan=lifespan,
)

# Allow the Vercel-hosted dashboard to call the backend
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Tighten in production if needed
    allow_credentials=True,
    allow_methods=["GET", "POST", "OPTIONS"],
    allow_headers=["*"],
)

# Register dashboard API routes
app.include_router(dashboard_router)


@app.get("/health")
async def health_check() -> dict[str, str]:
    """Health check endpoint for Railway."""
    return {"status": "healthy", "service": "bark"}


@app.post("/slack/events")
async def slack_events(request: Request) -> Response:
    """Handle Slack Events API requests."""
    settings = get_settings()

    # Get the raw body and headers
    body = await request.body()
    timestamp = request.headers.get("X-Slack-Request-Timestamp", "")
    signature = request.headers.get("X-Slack-Signature", "")
    print(body)
    print(timestamp)
    print(signature)

    # Parse event
    try:
        event: dict[str, Any] = json.loads(body)
    except json.JSONDecodeError:
        logger.error("Failed to parse JSON body")
        return Response(status_code=400, content="Invalid JSON")

    # URL verification challenge - respond immediately
    # Slack sends this during app setup to verify the endpoint
    if event.get("type") == "url_verification":
        logger.info("Responding to Slack URL verification challenge")
        return Response(
            content=json.dumps({"challenge": event.get("challenge")}),
            media_type="application/json",
        )

    # Verify signature for all other events
    if settings.slack_signing_secret:
        try:
            verify_slack_signature_from_body(
                body=body,
                timestamp=timestamp,
                signature=signature,
                signing_secret=settings.slack_signing_secret,
            )
        except Exception as e:
            logger.error(f"Signature verification failed: {e}")
            return Response(status_code=401, content="Unauthorized")

    logger.info(f"Received Slack event: {event.get('type')}")

    # Handle event
    if slack_handler:
        response = await slack_handler.handle_event(event)
        if response:
            return Response(
                content=json.dumps(response),
                media_type="application/json",
            )

    return Response(status_code=200)


def main() -> None:
    """Run the server."""
    import uvicorn

    settings = get_settings()
    uvicorn.run(
        "bark.server:app",
        host=settings.host,
        port=settings.port,
        reload=False,
    )


if __name__ == "__main__":
    main()
