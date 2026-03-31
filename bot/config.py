"""Application configuration via pydantic-settings."""

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # ── Telegram ──
    bot_token: str = ""
    webhook_url: str = ""
    admin_user_ids: str = ""  # comma-separated

    # ── Database ──
    postgres_host: str = "db"
    postgres_port: int = 5432
    postgres_db: str = "personalai"
    postgres_user: str = "personalai"
    postgres_password: str = "changeme"

    # ── Redis ──
    redis_host: str = "redis"
    redis_port: int = 6379
    redis_password: str = ""

    # ── LLM ──
    anthropic_api_key: str = ""
    gemini_api_key: str = ""
    openrouter_api_key: str = ""

    # ── Voice ──
    elevenlabs_api_key: str = ""
    deepgram_api_key: str = ""

    # ── External APIs ──
    yandex_weather_key: str = ""
    yandex_maps_key: str = ""
    perplexity_api_key: str = ""
    yandex_vision_key: str = ""

    # ── 1С ──
    one_c_base_url: str = ""
    one_c_username: str = ""
    one_c_password: str = ""

    # ── Persona ──
    default_persona: str = "sergiy"
    default_voice_id: str = "Maxim"

    # ── App ──
    environment: str = "development"
    log_level: str = "INFO"

    @property
    def database_url(self) -> str:
        return (
            f"postgresql+asyncpg://{self.postgres_user}:{self.postgres_password}"
            f"@{self.postgres_host}:{self.postgres_port}/{self.postgres_db}"
        )

    @property
    def database_url_raw(self) -> str:
        """For asyncpg direct connections (without SQLAlchemy)."""
        return (
            f"postgresql://{self.postgres_user}:{self.postgres_password}"
            f"@{self.postgres_host}:{self.postgres_port}/{self.postgres_db}"
        )

    @property
    def redis_url(self) -> str:
        password_part = f":{self.redis_password}@" if self.redis_password else ""
        return f"redis://{password_part}{self.redis_host}:{self.redis_port}/0"

    @property
    def is_production(self) -> bool:
        return self.environment == "production"

    @property
    def admin_ids(self) -> list[int]:
        if not self.admin_user_ids:
            return []
        return [int(x.strip()) for x in self.admin_user_ids.split(",") if x.strip()]


settings = Settings()
