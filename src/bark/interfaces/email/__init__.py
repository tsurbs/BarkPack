"""Email interface for Bark.

Provides a background worker that polls Gmail for incoming emails
sent to ops+bark@scottylabs.org and responds using the same AI
pipeline as the Slack integration.
"""

from bark.interfaces.email.handler import EmailHandler
from bark.interfaces.email.worker import EmailWorker

__all__ = ["EmailHandler", "EmailWorker"]
