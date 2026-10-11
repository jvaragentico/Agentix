from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="AGENTIX_", env_file=".env", extra="ignore")

    database_url: str = "postgresql+psycopg://agentix:agentix@localhost:5432/agentix"
    admin_token: str = ""
    enable_test_funding: bool = False
