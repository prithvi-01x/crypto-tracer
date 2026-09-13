"""
Unit and integration tests for application configuration, SecretStr masking,
and production invariant validation.
"""
import os
import subprocess
import sys
import pytest
from pydantic import SecretStr

from backend.app.config import Settings, RedisSecretStr, settings


def test_development_defaults_offline():
    """Verify development/test environment defaults load cleanly without network or credentials."""
    s = Settings(APP_ENV="development")
    assert s.APP_NAME == "Crypto-Tracer"
    assert s.APP_ENV == "development"
    assert isinstance(s.SECRET_KEY, SecretStr)
    assert isinstance(s.DATABASE_URL, SecretStr)
    assert isinstance(s.REDIS_URL, SecretStr)
    assert isinstance(s.TRON_API_KEY, SecretStr)


def test_secret_str_masking_in_repr():
    """Verify secrets are masked in repr and str to avoid accidental log leakage."""
    s = Settings(
        APP_ENV="development",
        SECRET_KEY="super-secret-key-12345678901234567890",
        DATABASE_URL="postgresql+asyncpg://user:mypassword@localhost:5432/db",
    )
    settings_repr = repr(s)
    assert "mypassword" not in settings_repr
    assert "super-secret-key" not in settings_repr
    assert "SecretStr('**********')" in settings_repr
    assert repr(s.SECRET_KEY) == "SecretStr('**********')"
    assert repr(s.DATABASE_URL) == "SecretStr('**********')"
    assert repr(s.REDIS_URL) == "SecretStr('**********')"


def test_secret_value_accessors():
    """Verify value properties and .get_secret_value() retrieve unmasked secrets when authorized."""
    raw_secret = "my-test-secret-key-0123456789012345"
    raw_db = "postgresql+asyncpg://admin:pass@remote:5432/db"
    s = Settings(
        APP_ENV="development",
        SECRET_KEY=raw_secret,
        DATABASE_URL=raw_db,
    )
    assert s.secret_key_value == raw_secret
    assert s.SECRET_KEY.get_secret_value() == raw_secret
    assert s.database_url_value == raw_db
    assert s.DATABASE_URL.get_secret_value() == raw_db


def test_redis_secret_str_compatibility():
    """Verify RedisSecretStr satisfies both SecretStr masking and str operations for redis connection pool."""
    r = RedisSecretStr("redis://default:secret@redis-host:6379/0")
    assert isinstance(r, SecretStr)
    assert isinstance(r, str)
    assert repr(r) == "SecretStr('**********')"
    assert r.get_secret_value() == "redis://default:secret@redis-host:6379/0"
    # urlparse / urllib requires isinstance(url, str)
    import urllib.parse
    parsed = urllib.parse.urlparse(r)
    assert parsed.scheme == "redis"
    assert parsed.port == 6379


def test_production_rejects_missing_or_default_secret_key(capsys):
    """Verify production mode rejects empty, default insecure, or short SECRET_KEY."""
    # 1. Default dev SECRET_KEY in production
    with pytest.raises(SystemExit) as excinfo:
        Settings(
            APP_ENV="production",
            DATABASE_URL="postgresql+asyncpg://prod_user:strong_password@db.internal:5432/prod_db",
        )
    assert excinfo.value.code == 1
    err = capsys.readouterr().err
    assert "CRITICAL CONFIGURATION ERROR" in err
    assert "SECRET_KEY" in err

    # 2. Short SECRET_KEY in production (< 32 chars)
    with pytest.raises(SystemExit) as excinfo:
        Settings(
            APP_ENV="production",
            SECRET_KEY="short-key-12345",
            DATABASE_URL="postgresql+asyncpg://prod_user:strong_password@db.internal:5432/prod_db",
        )
    assert excinfo.value.code == 1

    # 3. Empty SECRET_KEY
    with pytest.raises(SystemExit) as excinfo:
        Settings(
            APP_ENV="production",
            SECRET_KEY="",
            DATABASE_URL="postgresql+asyncpg://prod_user:strong_password@db.internal:5432/prod_db",
        )
    assert excinfo.value.code == 1


def test_production_rejects_insecure_database_url(capsys):
    """Verify production mode rejects default development credentials or SQLite."""
    # 1. Default dev database URL in production
    with pytest.raises(SystemExit) as excinfo:
        Settings(
            APP_ENV="production",
            SECRET_KEY="a" * 32,
            DATABASE_URL="postgresql+asyncpg://postgres:postgres@localhost:5432/crypto_tracer",
        )
    assert excinfo.value.code == 1
    err = capsys.readouterr().err
    assert "DATABASE_URL" in err

    # 2. SQLite in production
    with pytest.raises(SystemExit) as excinfo:
        Settings(
            APP_ENV="production",
            SECRET_KEY="a" * 32,
            DATABASE_URL="sqlite+aiosqlite:///prod.db",
        )
    assert excinfo.value.code == 1


def test_production_accepts_valid_configuration():
    """Verify production mode succeeds with properly supplied secrets."""
    valid_key = "a" * 48
    valid_db = "postgresql+asyncpg://prod_app:super_secure_pass_99@db.prod.internal:5432/crypto_tracer"
    s = Settings(
        APP_ENV="production",
        SECRET_KEY=valid_key,
        DATABASE_URL=valid_db,
    )
    assert s.APP_ENV == "production"
    assert s.secret_key_value == valid_key
    assert s.database_url_value == valid_db


def test_production_startup_subprocess_clean_exit_code_1():
    """Verify starting python with APP_ENV=production and no secrets cleanly terminates with code 1."""
    env = os.environ.copy()
    env["APP_ENV"] = "production"
    # Ensure clean env without inherited secrets
    env.pop("SECRET_KEY", None)
    env.pop("DATABASE_URL", None)

    cmd = [
        sys.executable,
        "-c",
        "from backend.app.config import load_settings; load_settings()",
    ]
    proc = subprocess.run(cmd, env=env, capture_output=True, text=True)
    assert proc.returncode == 1
    assert "CRITICAL CONFIGURATION ERROR" in proc.stderr
    assert "SECRET_KEY" in proc.stderr


def test_main_app_production_startup_subprocess_clean_exit_code_1():
    """Verify importing backend.app.main with APP_ENV=production and no secrets cleanly terminates with code 1."""
    env = os.environ.copy()
    env["APP_ENV"] = "production"
    env.pop("SECRET_KEY", None)
    env.pop("DATABASE_URL", None)

    cmd = [
        sys.executable,
        "-c",
        "from backend.app.main import app",
    ]
    proc = subprocess.run(cmd, env=env, capture_output=True, text=True)
    assert proc.returncode == 1
    assert "CRITICAL CONFIGURATION ERROR" in proc.stderr
