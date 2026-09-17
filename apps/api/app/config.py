from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    postgres_db: str
    postgres_user: str
    postgres_password: str
    postgres_port: int = 5432

    openai_api_key: str | None = None
    openai_model: str = "gpt-5.6-luna"
    openai_max_output_tokens: int = 700

    mcp_url: str = "http://127.0.0.1:8001/mcp"

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )


settings = Settings()
