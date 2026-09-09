from typing import List, Any
from pydantic import field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    APP_NAME: str = "Crypto-Tracer"
    APP_VERSION: str = "0.1.0"
    APP_ENV: str = "development"
    API_V1_STR: str = "/api/v1"
    
    # Database (PostgreSQL default, supports SQLite fallback for local test/dev)
    DATABASE_URL: str = "postgresql+asyncpg://postgres:postgres@localhost:5432/crypto_tracer"
    
    # Redis
    REDIS_URL: str = "redis://localhost:6379/0"
    
    # CORS
    CORS_ORIGINS: List[str] = [
        "http://localhost:5173",
        "http://127.0.0.1:5173",
        "http://localhost:3000",
        "http://127.0.0.1:3000",
        "http://localhost:8000",
        "http://127.0.0.1:8000",
        "http://localhost",
        "http://127.0.0.1",
    ]

    @field_validator("CORS_ORIGINS", mode="before")
    @classmethod
    def parse_cors_origins(cls, v: Any) -> List[str]:
        if isinstance(v, str) and not v.startswith("["):
            return [i.strip() for i in v.split(",") if i.strip()]
        return v
    
    # Logging
    LOG_LEVEL: str = "INFO"

    # Blockchain Ingestion (TRON / TronGrid)
    TRON_API_BASE_URL: str = "https://api.trongrid.io"
    TRON_API_KEY: str = ""
    TRON_USDT_CONTRACT: str = "TR7NHqjeKQxGTCi8q8ZY4pL8otSzgjLj6t"
    BLOCKCHAIN_CACHE_TTL_SECONDS: int = 300
    REPORTS_DIR: str = "data/reports"
    
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore"
    )


settings = Settings()
