from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    postgres_db: str
    postgres_user: str
    postgres_password: str
    postgres_port: int = 5432

    openai_api_key: str | None = None
    openai_model: str = "gpt-5.6-luna"
    openai_max_output_tokens: int = 700
    openai_timeout_seconds: float = 45.0
    openai_max_retries: int = 2

    mcp_url: str = "http://127.0.0.1:8001/mcp"
    mcp_connect_timeout_seconds: float = 2.0
    mcp_call_timeout_seconds: float = 5.0
    mcp_max_attempts: int = 3
    mcp_retry_base_delay_ms: int = 150
    mcp_circuit_failure_threshold: int = 3
    mcp_circuit_cooldown_seconds: float = 20.0

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )


settings = Settings()
