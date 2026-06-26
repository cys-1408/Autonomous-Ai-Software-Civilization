"""Central configuration for the communication services."""

from pydantic import Field, SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict


class ServiceSettings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_nested_delimiter="__",
        extra="ignore",
    )


class RedisSettings(ServiceSettings):
    url: str = "redis://localhost:6379/0"
    max_connections: int = 50
    stream_max_length: int = 100_000
    consumer_block_ms: int = 2_000
    delivery_attempts: int = 5


class DatabaseSettings(ServiceSettings):
    postgres_url: str = "postgresql+asyncpg://postgres:postgres@localhost:5432/ai_civilization"
    pool_size: int = 10
    max_overflow: int = 20
    create_schema: bool = True


class GRPCSettings(ServiceSettings):
    host: str = "0.0.0.0"
    agent_port: int = 50051
    reflection_enabled: bool = True
    shared_secret: SecretStr | None = None
    max_message_bytes: int = 4 * 1024 * 1024


class WebSocketSettings(ServiceSettings):
    host: str = "0.0.0.0"
    port: int = 8765
    auth_token: SecretStr | None = None
    ping_interval_seconds: int = 20
    ping_timeout_seconds: int = 20


class PrometheusSettings(ServiceSettings):
    enabled: bool = True
    host: str = "0.0.0.0"
    port: int = 9091


class Settings(ServiceSettings):
    """Root settings combining all sub-configurations."""

    project_name: str = "AI Civilization"
    environment: str = "development"
    debug: bool = False
    log_level: str = "INFO"

    redis: RedisSettings = Field(default_factory=RedisSettings)
    database: DatabaseSettings = Field(default_factory=DatabaseSettings)
    grpc: GRPCSettings = Field(default_factory=GRPCSettings)
    websocket: WebSocketSettings = Field(default_factory=WebSocketSettings)
    prometheus: PrometheusSettings = Field(default_factory=PrometheusSettings)


settings = Settings()
