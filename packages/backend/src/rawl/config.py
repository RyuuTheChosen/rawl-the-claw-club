from __future__ import annotations

from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    model_config = {"env_file": ".env", "env_file_encoding": "utf-8"}

    # Database
    database_url: str = "postgresql+asyncpg://rawl:rawl@localhost:5432/rawl"

    # Redis
    redis_url: str = "redis://localhost:6379/0"

    # S3 / MinIO
    s3_endpoint: str = "http://localhost:9000"
    s3_access_key: str = "minioadmin"
    s3_secret_key: str = "minioadmin"
    s3_bucket: str = "rawl-replays"
    s3_region: str = "us-east-1"

    # DIAMBRA
    diambra_host: str = "localhost"
    diambra_port: int = 50051
    diambra_rom_path: str = "/roms"
    diambra_image: str = "diambra/arena:latest"

    # CORS
    cors_origins: str = "http://localhost:3000"

    # Internal JWT (SSR)
    internal_jwt_secret: str = "change-me-in-production"
    internal_jwt_expiry_seconds: int = 300

    # Solana
    solana_rpc_url: str = "http://localhost:8899"
    solana_ws_url: str = "ws://localhost:8900"
    oracle_keypair_path: str = "./oracle-keypair.json"
    program_id: str = "RawL1111111111111111111111111111111111111111"
    solana_confirm_timeout: int = 30
    solana_max_retries: int = 3

    # Match defaults
    default_match_format: int = 3
    streaming_fps: int = 30
    data_channel_hz: int = 10
    heartbeat_interval_seconds: int = 15

    # Training tiers
    training_tier_free_timesteps: int = 500_000
    training_tier_standard_timesteps: int = 5_000_000
    training_tier_pro_timesteps: int = 50_000_000
    training_tier_free_gpu: str = "T4"
    training_tier_standard_gpu: str = "T4"
    training_tier_pro_gpu: str = "A10G"
    training_max_concurrent_free: int = 1
    training_max_concurrent_standard: int = 2
    training_max_concurrent_pro: int = 4

    # Rate limiting
    rate_limit_enabled: bool = True

    # Logging
    log_level: str = "INFO"
    log_format: str = "json"

    @property
    def cors_origin_list(self) -> list[str]:
        return [o.strip() for o in self.cors_origins.split(",")]


settings = Settings()
