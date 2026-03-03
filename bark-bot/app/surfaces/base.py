from abc import ABC, abstractmethod
from typing import Any

class BaseSurface(ABC):
    """
    Abstract base class for all Bark Bot surfaces (Web, Slack, Email, CLI).
    """

    @abstractmethod
    async def receive_event(self, event_data: Any) -> Any:
        """
        Receive an event from the surface transport layer.
        Must normalize the input into a standard format.
        """
        pass

    @abstractmethod
    async def authenticate(self, request_data: Any) -> str:
        """
        Extract identity from the request (JWT, PAT, Slack ID).
        Should return a standard Internal User Identity.
        Raises an exception or returns a challenge flow if unauthenticated.
        """
        pass

    @abstractmethod
    async def respond(self, response_data: Any) -> Any:
        """
        Format and send a response back through the specific surface transport.
        """
        pass
