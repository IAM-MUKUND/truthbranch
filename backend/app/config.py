from pydantic_settings import BaseSettings, SettingsConfigDict
from functools import lru_cache


class Settings(BaseSettings):
    falkordb_host: str = "localhost"
    falkordb_port: int = 6380
    groq_api_key: str = ""
    groq_api_key1: str = ""
    groq_api_key2: str = ""
    groq_api_key3: str = ""
    groq_api_key4: str = ""
    groq_model: str = "openai/gpt-oss-120b"
    groq_heavy_model: str = "openai/gpt-oss-120b"  # For deep reasoning, tool calling, and lineage analysis
    groq_light_model: str = "openai/gpt-oss-20b"    # For fast text formatting, summaries, and light tasks
    agent_mode: str = "scripted"

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore"
    )


@lru_cache
def get_settings() -> Settings:
    return Settings()
