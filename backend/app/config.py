from pydantic_settings import BaseSettings, SettingsConfigDict
from functools import lru_cache


class Settings(BaseSettings):
    falkordb_host: str = "localhost"
    falkordb_port: int = 6380
    groq_api_key: str = ""
    groq_model: str = "llama-3.3-70b-versatile"
    agent_mode: str = "scripted"

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore"
    )


@lru_cache
def get_settings() -> Settings:
    return Settings()
