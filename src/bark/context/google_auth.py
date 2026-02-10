"""Shared Google Workspace authentication module.

Provides a single OAuth2 credential set with all required scopes,
and builds/caches service objects for each Google API.
"""

import json
import logging
import os
from typing import Any

from google.auth.transport.requests import Request
from google.oauth2 import service_account
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build

logger = logging.getLogger(__name__)

# All scopes needed across Google Workspace APIs.
# If modifying these scopes, delete token.json to re-authenticate.
SCOPES = [
    # Google Drive (full access, upgraded from readonly)
    "https://www.googleapis.com/auth/drive",
    # Drive Activity
    "https://www.googleapis.com/auth/drive.activity.readonly",
    # Drive Labels
    "https://www.googleapis.com/auth/drive.labels.readonly",
    # Gmail
    "https://www.googleapis.com/auth/gmail.modify",
    # Gmail Postmaster
    "https://www.googleapis.com/auth/postmaster.readonly",
    # Google Calendar
    "https://www.googleapis.com/auth/calendar",
    # Google Chat
    "https://www.googleapis.com/auth/chat.spaces",
    "https://www.googleapis.com/auth/chat.messages",
    # Google Docs
    "https://www.googleapis.com/auth/documents",
    # Google Sheets (used by Docs/Sheets tools)
    "https://www.googleapis.com/auth/spreadsheets",
    # Google Forms
    "https://www.googleapis.com/auth/forms.body.readonly",
    "https://www.googleapis.com/auth/forms.responses.readonly",
    # Admin SDK
    "https://www.googleapis.com/auth/admin.directory.user.readonly",
    "https://www.googleapis.com/auth/admin.directory.group.readonly",
    # Apps Script
    "https://www.googleapis.com/auth/script.projects",
    # Google Meet
    "https://www.googleapis.com/auth/meetings.space.created",
    "https://www.googleapis.com/auth/meetings.space.readonly",
]


class GoogleAuth:
    """Shared Google Workspace authentication manager.

    Maintains a single set of credentials and builds service objects
    for each API on demand. Service objects are cached after creation.
    """

    def __init__(
        self,
        credentials_file: str = "credentials.json",
        credentials_json: str | None = None,
        token_json: str | None = None,
        token_file: str = "token.json",
    ) -> None:
        self.credentials_file = credentials_file
        self.credentials_json = credentials_json
        self.token_json = token_json
        self.token_file = token_file
        self._creds: Credentials | None = None
        self._services: dict[str, Any] = {}

    def _get_credentials(self) -> Credentials:
        """Get or create OAuth2 credentials with all workspace scopes."""
        if self._creds and self._creds.valid:
            return self._creds

        creds = None

        # 1. Try Service Account from JSON string
        if self.credentials_json:
            try:
                info = json.loads(self.credentials_json)
                creds = service_account.Credentials.from_service_account_info(
                    info, scopes=SCOPES
                )
                logger.info("Loaded Service Account credentials from JSON string")
            except Exception as e:
                logger.warning(f"Failed to load Service Account from JSON string: {e}")

        # 2. Try Service Account from file
        if not creds and self.credentials_file and os.path.exists(self.credentials_file):
            try:
                creds = service_account.Credentials.from_service_account_file(
                    self.credentials_file, scopes=SCOPES
                )
                logger.info("Loaded Service Account credentials from file")
            except ValueError:
                # Not a service account file — fall through to user creds
                pass

        if not creds:
            # 3. Try User Token from JSON string
            if self.token_json:
                try:
                    info = json.loads(self.token_json)
                    creds = Credentials.from_authorized_user_info(info, SCOPES)
                    logger.info("Loaded User credentials from JSON string")
                except Exception as e:
                    logger.warning(f"Failed to load User credentials from JSON string: {e}")

            # 4. Try User Token from file
            if (not creds or not creds.valid) and os.path.exists(self.token_file):
                creds = Credentials.from_authorized_user_file(self.token_file, SCOPES)

            # Refresh or re-authenticate if needed
            if not creds or not creds.valid:
                if creds and creds.expired and creds.refresh_token:
                    creds.refresh(Request())
                else:
                    if not self.credentials_file or not os.path.exists(self.credentials_file):
                        raise FileNotFoundError(
                            f"Credentials file not found: {self.credentials_file}"
                        )
                    flow = InstalledAppFlow.from_client_secrets_file(
                        self.credentials_file, SCOPES
                    )
                    creds = flow.run_local_server(port=0)

                # Save token for next run
                if self.token_file:
                    with open(self.token_file, "w") as token:
                        token.write(creds.to_json())
                    logger.info("Saved updated token to %s", self.token_file)

        self._creds = creds
        return self._creds

    def get_service(self, api: str, version: str) -> Any:
        """Get a Google API service object, creating and caching it if needed.

        Args:
            api: API name (e.g. "drive", "gmail", "calendar")
            version: API version (e.g. "v3", "v1")

        Returns:
            Google API service resource object
        """
        key = f"{api}:{version}"
        if key not in self._services:
            creds = self._get_credentials()
            self._services[key] = build(api, version, credentials=creds)
            logger.info("Built %s %s service", api, version)
        return self._services[key]

    # Convenience properties for commonly used services
    @property
    def drive(self) -> Any:
        return self.get_service("drive", "v3")

    @property
    def gmail(self) -> Any:
        return self.get_service("gmail", "v1")

    @property
    def calendar(self) -> Any:
        return self.get_service("calendar", "v3")

    @property
    def docs(self) -> Any:
        return self.get_service("docs", "v1")

    @property
    def sheets(self) -> Any:
        return self.get_service("sheets", "v4")

    @property
    def forms(self) -> Any:
        return self.get_service("forms", "v1")

    @property
    def admin(self) -> Any:
        return self.get_service("admin", "directory_v1")

    @property
    def chat(self) -> Any:
        return self.get_service("chat", "v1")

    @property
    def meet(self) -> Any:
        return self.get_service("meet", "v2")

    @property
    def drive_activity(self) -> Any:
        return self.get_service("driveactivity", "v2")

    @property
    def drive_labels(self) -> Any:
        return self.get_service("drivelabels", "v2")

    @property
    def script(self) -> Any:
        return self.get_service("script", "v1")

    @property
    def postmaster(self) -> Any:
        return self.get_service("gmailpostmastertools", "v1")


# ---------------------------------------------------------------------------
# Global singleton
# ---------------------------------------------------------------------------
_auth: GoogleAuth | None = None


def get_google_auth() -> GoogleAuth:
    """Get the global GoogleAuth instance, creating it lazily from settings."""
    global _auth
    if _auth is None:
        from bark.core.config import get_settings

        settings = get_settings()
        _auth = GoogleAuth(
            credentials_file=settings.google_drive_credentials_file,
            credentials_json=settings.google_drive_credentials_json,
            token_json=settings.google_drive_token_json,
        )
    return _auth
