import os
import sys
from typing import List, Any, Optional, Union
from pydantic import SecretStr, field_validator, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

# Canonical Default Multi-Tenant Partitioning Constants
DEFAULT_TENANT_ID: str = "TN-STATE"
DEFAULT_DISTRICT_ID: str = "CYBER-CRIME-HQ"
DEFAULT_POLICE_STATION_ID: str = "PS-CENTRAL"


class RedisSecretStr(SecretStr, str):
    """
    Hybrid SecretStr and str type for REDIS_URL.
    Ensures isinstance(val, SecretStr) is True with masked __repr__,
    while remaining directly usable as a str for redis.ConnectionPool.from_url.
    """
    def __new__(cls, value: Any = ""):
        if isinstance(value, SecretStr):
            value = value.get_secret_value()
        return super(SecretStr, cls).__new__(cls, str(value or ""))

    def __init__(self, value: Any = ""):
        if isinstance(value, SecretStr):
            value = value.get_secret_value()
        super().__init__(str(value or ""))

    def __repr__(self) -> str:
        return "SecretStr('**********')"

    def __str__(self) -> str:
        return super(SecretStr, self).__str__()


class Settings(BaseSettings):
    APP_NAME: str = "Crypto-Tracer"
    APP_VERSION: str = "0.1.0"
    APP_ENV: str = "development"
    API_V1_STR: str = "/api/v1"

    # Security & Cryptography
    SECRET_KEY: SecretStr = SecretStr("insecure-dev-secret-key-change-me-for-production-use-only-0000")
    
    # Database (PostgreSQL default, supports SQLite fallback for local test/dev)
    DATABASE_URL: SecretStr = SecretStr("postgresql+asyncpg://postgres:postgres@localhost:5432/crypto_tracer")
    DB_POOL_SIZE: int = 20
    DB_MAX_OVERFLOW: int = 10
    DB_POOL_RECYCLE: int = 3600
    DB_POOL_PRE_PING: bool = True
    DB_PGBOUNCER_MODE: bool = False
    
    # Redis
    REDIS_URL: SecretStr = SecretStr("redis://localhost:6379/0")
    
    # CORS & Hosts
    CORS_ORIGINS: Union[List[str], str] = [
        "http://localhost:5173",
        "http://127.0.0.1:5173",
        "http://localhost:3000",
        "http://127.0.0.1:3000",
        "http://localhost:8000",
        "http://127.0.0.1:8000",
        "http://localhost",
        "http://127.0.0.1",
    ]
    ALLOWED_HOSTS: Union[List[str], str] = ["*"]

    # Logging & Observability
    LOG_LEVEL: str = "INFO"
    LOG_FORMAT: str = "text"

    # Transport Security
    SECURE_HSTS_ENABLED: Optional[bool] = None

    # Execution Mode & Blockchain Ingestion (TRON / TronGrid)
    DEFAULT_EXECUTION_MODE: str = "LIVE"
    TRON_API_BASE_URL: str = "https://api.trongrid.io"
    TRON_FALLBACK_API_URLS: Union[List[str], str] = []
    TRON_API_KEY: SecretStr = SecretStr("")
    TRON_USDT_CONTRACT: str = "TR7NHqjeKQxGTCi8q8ZY4pL8otSzgjLj6t"
    TRON_HTTP_TIMEOUT_SECONDS: float = 10.0
    TRON_MAX_RETRIES: int = 3
    BLOCKCHAIN_CACHE_TTL_SECONDS: int = 300
    REPORTS_DIR: str = "data/reports"

    # Phase 1 Auth & OIDC Engine
    JWT_ALGORITHM: str = "HS256"
    JWT_SECRET_KEY: Optional[SecretStr] = None
    JWT_PUBLIC_KEY: Optional[str] = None
    JWT_PUBLIC_KEY_PATH: Optional[str] = None
    JWT_AUDIENCE: Optional[str] = None
    OIDC_ISSUER: Optional[str] = None
    OIDC_CLIENT_ID: Optional[str] = None
    OIDC_JWKS_URL: Optional[str] = None
    OIDC_AUDIENCE: Optional[str] = None

    # DPDP Act 2023 PII Encryption at Rest
    ENCRYPTION_KEY: Optional[SecretStr] = None

    @field_validator("CORS_ORIGINS", mode="after")
    @classmethod
    def parse_cors_origins(cls, v: Any) -> List[str]:
        if isinstance(v, str):
            v_str = v.strip()
            if v_str.startswith("["):
                import json
                try:
                    parsed = json.loads(v_str)
                    if isinstance(parsed, list):
                        return [str(i).strip() for i in parsed if str(i).strip()]
                except Exception:
                    pass
            return [i.strip() for i in v_str.split(",") if i.strip()]
        return [str(i).strip() for i in v] if isinstance(v, list) else []

    @field_validator("ALLOWED_HOSTS", mode="after")
    @classmethod
    def parse_allowed_hosts(cls, v: Any) -> List[str]:
        if isinstance(v, str):
            v_str = v.strip()
            if v_str.startswith("["):
                import json
                try:
                    parsed = json.loads(v_str)
                    if isinstance(parsed, list):
                        return [str(i).strip() for i in parsed if str(i).strip()]
                except Exception:
                    pass
            return [i.strip() for i in v_str.split(",") if i.strip()]
        return [str(i).strip() for i in v] if isinstance(v, list) else []

    @field_validator("TRON_FALLBACK_API_URLS", mode="after")
    @classmethod
    def parse_fallback_urls(cls, v: Any) -> List[str]:
        if isinstance(v, str):
            v_str = v.strip()
            if v_str.startswith("["):
                import json
                try:
                    parsed = json.loads(v_str)
                    if isinstance(parsed, list):
                        return [str(i).strip() for i in parsed if str(i).strip()]
                except Exception:
                    pass
            return [i.strip() for i in v_str.split(",") if i.strip()]
        return [str(i).strip() for i in v] if isinstance(v, list) else []

    @field_validator("REDIS_URL", mode="after")
    @classmethod
    def wrap_redis(cls, v: Any) -> RedisSecretStr:
        if isinstance(v, SecretStr):
            return RedisSecretStr(v.get_secret_value())
        return RedisSecretStr(str(v or ""))

    @field_validator("SECRET_KEY", "DATABASE_URL", "TRON_API_KEY", "ENCRYPTION_KEY", "JWT_SECRET_KEY", mode="before")
    @classmethod
    def wrap_secrets(cls, v: Any) -> Any:
        if isinstance(v, str):
            return SecretStr(v)
        return v

    @property
    def secret_key_value(self) -> str:
        return self.SECRET_KEY.get_secret_value() if isinstance(self.SECRET_KEY, SecretStr) else str(self.SECRET_KEY or "")

    @property
    def database_url_value(self) -> str:
        return self.DATABASE_URL.get_secret_value() if isinstance(self.DATABASE_URL, SecretStr) else str(self.DATABASE_URL or "")

    @property
    def redis_url_value(self) -> str:
        return self.REDIS_URL.get_secret_value() if isinstance(self.REDIS_URL, SecretStr) else str(self.REDIS_URL or "")

    @property
    def tron_api_key_value(self) -> str:
        return self.TRON_API_KEY.get_secret_value() if isinstance(self.TRON_API_KEY, SecretStr) else str(self.TRON_API_KEY or "")

    @property
    def encryption_key_value(self) -> str:
        if self.ENCRYPTION_KEY and isinstance(self.ENCRYPTION_KEY, SecretStr):
            val = self.ENCRYPTION_KEY.get_secret_value().strip()
            if val:
                return val
        return self.secret_key_value

    @property
    def jwt_secret_key_value(self) -> str:
        if self.JWT_SECRET_KEY and isinstance(self.JWT_SECRET_KEY, SecretStr):
            val = self.JWT_SECRET_KEY.get_secret_value().strip()
            if val:
                return val
        return self.secret_key_value

    def validate_production_invariants(self) -> None:
        """
        Validate production configuration requirements.
        Cleanly exits with a descriptive stderr message and exit code 1 if invariants fail.
        """
        if self.APP_ENV.lower() != "production":
            return

        violations: List[str] = []

        sec_val = self.secret_key_value.strip()
        if not sec_val:
            violations.append("SECRET_KEY is empty or missing.")
        elif sec_val.startswith("insecure-dev"):
            violations.append("SECRET_KEY cannot use default development prefix ('insecure-dev').")
        elif "change-me" in sec_val.lower():
            violations.append("SECRET_KEY cannot contain placeholder 'change-me'.")
        elif len(sec_val) < 32:
            violations.append(f"SECRET_KEY must be at least 32 characters long (found {len(sec_val)}).")

        db_val = self.database_url_value.strip()
        if not db_val:
            violations.append("DATABASE_URL is empty or missing.")
        elif "sqlite" in db_val.lower():
            violations.append("DATABASE_URL cannot use SQLite in production.")
        elif "postgres:postgres@localhost" in db_val:
            violations.append("DATABASE_URL cannot use default development credentials (postgres:postgres@localhost).")

        if self.JWT_ALGORITHM.upper() == "RS256":
            has_rs256_key = bool(
                (self.JWT_PUBLIC_KEY and self.JWT_PUBLIC_KEY.strip())
                or (self.JWT_PUBLIC_KEY_PATH and os.path.exists(self.JWT_PUBLIC_KEY_PATH))
                or (self.OIDC_JWKS_URL and self.OIDC_JWKS_URL.strip().startswith("https://"))
                or (self.OIDC_ISSUER and self.OIDC_ISSUER.strip().startswith("https://"))
            )
            if not has_rs256_key:
                violations.append(
                    "JWT_ALGORITHM is RS256 in production, but no verification key source is configured "
                    "(set JWT_PUBLIC_KEY, JWT_PUBLIC_KEY_PATH, OIDC_JWKS_URL, or OIDC_ISSUER)."
                )

        if violations:
            banner = (
                "\n"
                + "=" * 80 + "\n"
                + "CRITICAL CONFIGURATION ERROR: Production Environment Invariants Violated\n"
                + "=" * 80 + "\n"
                + "The application cannot start in APP_ENV=production due to the following security violations:\n"
                + "\n".join(f"  - {violation}" for violation in violations) + "\n"
                + "=" * 80 + "\n\n"
            )
            sys.stderr.write(banner)
            sys.stderr.flush()
            sys.exit(1)

    @model_validator(mode="after")
    def _enforce_production_invariants(self) -> "Settings":
        self.validate_production_invariants()
        return self

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )


def load_settings() -> Settings:
    """Load settings and validate production invariants, cleanly exiting on validation failure."""
    try:
        s = Settings()
        return s
    except SystemExit:
        raise
    except Exception as err:
        sys.stderr.write(
            f"\n================================================================================\n"
            f"CRITICAL CONFIGURATION ERROR: Failed to load application settings\n"
            f"================================================================================\n"
            f"{err}\n"
            f"================================================================================\n\n"
        )
        sys.stderr.flush()
        sys.exit(1)


settings = load_settings()
