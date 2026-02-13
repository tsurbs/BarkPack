"""In-memory activity logger for the observability dashboard.

Records recent Bark operations (tool calls, memory writes, searches, etc.)
and exposes them via a simple API for the dashboard.
"""

import logging
import threading
import time
from collections import deque
from dataclasses import asdict, dataclass, field
from typing import Any

logger = logging.getLogger(__name__)

MAX_ENTRIES = 200


@dataclass
class ActivityEntry:
    """A single activity log entry."""

    id: int
    action: str
    detail: str
    committee: str
    timestamp: float = field(default_factory=time.time)

    def to_dict(self) -> dict[str, Any]:
        """Convert to dict with human-readable relative time."""
        d = asdict(self)
        d["time"] = _relative_time(self.timestamp)
        return d


class ActivityLogger:
    """Thread-safe, in-memory ring buffer of recent Bark operations."""

    def __init__(self, max_entries: int = MAX_ENTRIES) -> None:
        self._entries: deque[ActivityEntry] = deque(maxlen=max_entries)
        self._lock = threading.Lock()
        self._counter = 0

    def log(self, action: str, detail: str, committee: str = "") -> None:
        """Record an activity entry.

        Args:
            action: Short action label (e.g. "Memory saved", "Wiki queried")
            detail: Descriptive detail of what happened
            committee: Related committee slug (optional)
        """
        with self._lock:
            self._counter += 1
            entry = ActivityEntry(
                id=self._counter,
                action=action,
                detail=detail,
                committee=committee,
            )
            self._entries.append(entry)
            logger.debug("Activity logged: %s — %s", action, detail)

    def get_recent(self, limit: int = 50) -> list[dict[str, Any]]:
        """Return the most recent activity entries (newest first).

        Args:
            limit: Maximum number of entries to return

        Returns:
            List of activity dicts with relative timestamps
        """
        with self._lock:
            entries = list(self._entries)

        # Newest first
        entries.reverse()
        return [e.to_dict() for e in entries[:limit]]

    def count(self) -> int:
        """Total number of activities logged since start."""
        return self._counter


def _relative_time(ts: float) -> str:
    """Convert a Unix timestamp to a human-readable relative string."""
    diff = time.time() - ts
    if diff < 60:
        return "just now"
    elif diff < 3600:
        mins = int(diff / 60)
        return f"{mins} minute{'s' if mins != 1 else ''} ago"
    elif diff < 86400:
        hours = int(diff / 3600)
        return f"{hours} hour{'s' if hours != 1 else ''} ago"
    else:
        days = int(diff / 86400)
        return f"{days} day{'s' if days != 1 else ''} ago"


# ---------------------------------------------------------------------------
# Global singleton
# ---------------------------------------------------------------------------
_activity_logger: ActivityLogger | None = None


def get_activity_logger() -> ActivityLogger:
    """Get the global ActivityLogger instance."""
    global _activity_logger
    if _activity_logger is None:
        _activity_logger = ActivityLogger()
    return _activity_logger
