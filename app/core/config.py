from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    database_url: str = "postgresql+psycopg://gateway@localhost:5433/gateway"
    redis_url: str = "redis://localhost:6380/0"
    jwt_secret: str = ""
    demo_access_key: str = ""
    jwt_ttl_minutes: int = 30
    log_level: str = "INFO"
    downstream_timeout_seconds: float = 2.0
    rate_limit_per_minute: int = 10
    circuit_failure_threshold: int = 3
    circuit_cooldown_seconds: int = 30


@lru_cache
def get_settings() -> Settings:
    return Settings()

