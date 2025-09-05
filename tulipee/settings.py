from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict

class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
    )
    zulip_url: str
    api_key: str
    email: str
    # Log level via env `LOG_LEVEL` (e.g., DEBUG, INFO)
    log_level: str = "DEBUG"

    # YouTrack (optional; required for issue creation handler)
    youtrack_url: str | None = None
    youtrack_token: str | None = None

    # LLM provider (OpenAI-compatible; optional)
    openai_api_key: str | None = None
    # Default to OpenRouter; override if using OpenAI-native
    openai_base_url: str = "https://openrouter.ai/api/v1"
    openai_model: str = "openrouter/auto"
    # Optional OpenRouter headers for rate/attribution
    openai_http_referer: str | None = None
    openai_app_title: str | None = None
