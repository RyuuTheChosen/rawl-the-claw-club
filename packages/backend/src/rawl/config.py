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

    # Emulation (stable-retro)
    retro_game: str = "StreetFighterIISpecialChampionEdition-Genesis-v0"
    retro_integration_path: str = ""
    retro_obs_size: int = 256

    # CORS
    cors_origins: str = "http://localhost:3000"

    # Internal JWT (SSR)
    internal_jwt_secret: str = "change-me-in-production"
    internal_jwt_expiry_seconds: int = 300

    # Solana
    solana_rpc_url: str = "http://localhost:8899"
    solana_ws_url: str = "ws://localhost:8900"
    oracle_keypair_path: str = "./oracle-keypair.json"
    program_id: str = "AQCBqFfB3hH6CMRNk745NputeXnK7L8nvj15zkAZpd7K"
    solana_confirm_timeout: int = 30
    solana_max_retries: int = 3

    # Match defaults
    default_match_format: int = 3
    streaming_fps: int = 30
    data_channel_hz: int = 10
    heartbeat_interval_seconds: int = 15
    pre_match_delay_seconds: int = 60

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

    # Elo rating system
    elo_rating_floor: float = 800.0
    elo_k_calibration: int = 40
    elo_k_established: int = 20
    elo_k_elite: int = 16
    elo_elite_threshold: float = 1800.0
    elo_calibration_match_threshold: int = 10

    # Calibration
    calibration_reference_elos: str = "1000,1100,1200,1400,1600"
    calibration_min_success: int = 3
    calibration_max_retries: int = 2

    # Seasonal reset (quarterly: Jan 1, Apr 1, Jul 1, Oct 1)
    seasonal_reset_cron_month: str = "1,4,7,10"
    seasonal_reset_cron_day: str = "1"
    seasonal_reset_cron_hour: str = "0"
    seasonal_reset_cron_minute: str = "0"

    # Rate limiting
    rate_limit_enabled: bool = True

    # Logging
    log_level: str = "INFO"
    log_format: str = "json"

    @property
    def cors_origin_list(self) -> list[str]:
        return [o.strip() for o in self.cors_origins.split(",")]

    @property
    def calibration_reference_elo_list(self) -> list[int]:
        return [int(e.strip()) for e in self.calibration_reference_elos.split(",")]


settings = Settings()
