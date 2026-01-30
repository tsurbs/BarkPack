"""Configuration management using Pydantic Settings."""

from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application settings loaded from environment variables."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # OpenRouter Configuration
    openrouter_api_key: str = ""
    openrouter_model: str = "moonshotai/kimi-k2.5"
    openrouter_base_url: str = "https://openrouter.ai/api/v1"

    # Slack Configuration
    slack_bot_token: str = ""
    slack_signing_secret: str = ""

    # Notion Configuration
    notion_api_key: str = ""

    # Google Drive Configuration
    google_drive_credentials_file: str = "credentials.json"
    google_drive_credentials_json: str | None = None
    google_drive_token_json: str | None = None
    google_drive_folder_id: str | None = None
    google_drive_exclude_folder_ids: str = ""  # Comma-separated folder IDs to exclude

    # Server Configuration
    host: str = "0.0.0.0"
    port: int = 8000

    # Context Engine Configuration
    chroma_host: str = "localhost"
    chroma_port: int = 8000
    wiki_repo_url: str = "https://github.com/ScottyLabs/wiki.wiki.git"
    embedding_model: str = "openai/text-embedding-3-small"
    summarization_model: str = "google/gemini-2.0-flash-lite-001"

    # Bot Configuration
    system_prompt: str = """You are Bark, a helpful assistant for ScottyLabs (scottylabs.org). 
You are friendly, concise, and helpful. Your stored memories are automatically shown above.

**Tools available:**
- search_wiki: Search the ScottyLabs wiki for processes, projects, and policies
- search_notion: Search Notion pages for meeting notes, project docs, and more
- search_drive: Search Google Drive for documents, spreadsheets, presentations
- refresh_context: Refresh wiki content from GitHub (only needed if wiki is stale)
- write_memory: Save important info (names, projects, preferences, decisions, deadlines)
- delete_memory: Remove outdated memories
- no_reply: Use when your response isn't needed (message not directed at you)

**Guidelines:**
- ACTIVELY save new information to memory when you learn something worth remembering
- Use search_wiki for ScottyLabs-specific questions
- Use no_reply when you're not being addressed or wouldn't add value
- Keep responses clear and concise. Use Slack-compatible markdown."""


@lru_cache
def get_settings() -> Settings:
    """Get cached settings instance."""
    return Settings()
