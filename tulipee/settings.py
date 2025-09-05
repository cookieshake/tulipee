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
