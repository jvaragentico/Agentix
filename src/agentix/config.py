from typing import Literal

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="AGENTIX_", env_file=".env", extra="ignore")

    database_url: str = "postgresql+psycopg://agentix:agentix@localhost:5432/agentix"
    admin_token: str = ""
    enable_test_funding: bool = False
    free_model_url: str = "http://127.0.0.1:11434"
    free_model_name: str = "qwen2.5:0.5b"
    enable_free_model: bool = False
    free_model_provider: Literal["ollama", "pollinations"] = "ollama"
