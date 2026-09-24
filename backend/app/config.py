"""
Application settings loaded from environment variables.
Uses pydantic-settings for validation and type casting.
"""

from __future__ import annotations

import json
import os
import sys
from functools import lru_cache
from typing import List

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

_INSECURE_JWT_DEFAULTS = {"CHANGE-ME-IN-PRODUCTION", "", "secret", "changeme"}


class Settings(BaseSettings):
    """Central configuration — every value has a sensible default for local dev."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    # ── App ───────────────────────────────────────────────────
    APP_NAME: str = "EscalasPT"
    APP_ENV: str = "production"
    APP_DEBUG: bool = False
    LOG_LEVEL: str = "INFO"

    # ── Runtime ───────────────────────────────────────────────
    # True on Vercel, which sets VERCEL=1 in every function. Each instance
    # there is short-lived and may be frozen between requests, so nothing can
    # hold a connection pool or run a background loop — see database.py and
    # the lifespan in main.py.
    SERVERLESS: bool = Field(default_factory=lambda: bool(os.getenv("VERCEL")))

    # ── Database ──────────────────────────────────────────────
    DATABASE_URL: str = "postgresql+asyncpg://user:pass@localhost:5432/escalaspt"
    # Supabase only accepts TLS from outside its network. asyncpg ignores the
    # sslmode= parameter in the connection strings Supabase hands out, so it
    # is asked for here instead.
    DATABASE_SSL: bool = False

    # ── Redis ─────────────────────────────────────────────────
    # Holds the rate-limit counters. "memory://" keeps them in the process
    # instead: on serverless that means per instance, so the limits are
    # looser than they read — a stopgap until a Redis (Upstash) is attached.
    # Login stays protected by the account lockout, which lives in Postgres.
    REDIS_URL: str = "redis://:pass@localhost:6379/0"

    # ── Supabase Realtime ─────────────────────────────────────
    # Replaces the /ws endpoint where the API cannot hold a socket open. All
    # three empty means realtime is off and the frontend uses /ws, as before.
    # The API sends through realtime.send() in the database, so there is no
    # secret key here — see app/services/realtime.py.
    SUPABASE_URL: str = ""
    SUPABASE_PUBLISHABLE_KEY: str = ""  # handed to the browser; public by design
    # Channel names are derived from this, so knowing a user's id is not
    # enough to listen in on their channel.
    REALTIME_CHANNEL_SECRET: str = ""

    # ── Scheduled jobs ────────────────────────────────────────
    # Vercel Cron sends it as "Authorization: Bearer <CRON_SECRET>".
    CRON_SECRET: str = ""

    # ── Caderno de Serviço ────────────────────────────────
    # Chave partilhada com que o Caderno pergunta o turno do dia de um
    # militar (app/routers/integracao.py). Vazia: a ponte está desligada.
    CADERNO_INTEGRATION_KEY: str = ""

    @field_validator("DATABASE_URL")
    @classmethod
    def use_asyncpg_driver(cls, v: str) -> str:
        # Supabase, Neon and the Vercel integrations all give out plain
        # postgres:// URLs. The engine is async and needs the asyncpg driver
        # named; the libpq-only query parameters would be rejected by asyncpg.
        for prefix in ("postgres://", "postgresql://"):
            if v.startswith(prefix):
                v = "postgresql+asyncpg://" + v[len(prefix):]
                break
        if v.startswith("postgresql+asyncpg://") and "?" in v:
            base, query = v.split("?", 1)
            kept = [p for p in query.split("&") if p.split("=", 1)[0] not in {"sslmode", "pgbouncer", "supa"}]
            v = base + ("?" + "&".join(kept) if kept else "")
        return v

    @property
    def realtime_enabled(self) -> bool:
        return all((
            self.SUPABASE_URL,
            self.SUPABASE_PUBLISHABLE_KEY,
            self.REALTIME_CHANNEL_SECRET,
        ))

    # ── JWT ───────────────────────────────────────────────────
    JWT_SECRET_KEY: str = "CHANGE-ME-IN-PRODUCTION"
    JWT_ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 15
    REFRESH_TOKEN_EXPIRE_DAYS: int = 7

    # ── TOTP ──────────────────────────────────────────────────
    TOTP_ISSUER_NAME: str = "EscalasPT"
    TOTP_ENCRYPTION_KEY: str = ""  # Fernet key for encrypting totp_secret at rest

    # ── Account Lockout ───────────────────────────────────────
    ACCOUNT_LOCKOUT_ATTEMPTS: int = 5
    ACCOUNT_LOCKOUT_MINUTES: int = 15
    MAX_CONCURRENT_SESSIONS: int = 3

    # ── CORS ──────────────────────────────────────────────────
    CORS_ORIGINS: str = '["http://localhost:3000","http://localhost:5173"]'

    @property
    def cors_origins_list(self) -> List[str]:
        return json.loads(self.CORS_ORIGINS)

    @field_validator("CORS_ORIGINS")
    @classmethod
    def validate_cors_origins(cls, v: str, info) -> str:
        env = info.data.get("APP_ENV", "production")
        origins = json.loads(v) if v else []
        if env != "development":
            unsafe = [o for o in origins if "localhost" in o or "127.0.0.1" in o]
            if unsafe:
                # Strip localhost origins in non-development environments
                safe_origins = [o for o in origins if "localhost" not in o and "127.0.0.1" not in o]
                print(
                    f"WARNING: CORS_ORIGINS contained localhost entries in {env} mode: {unsafe}. "
                    "They have been removed automatically.",
                    file=sys.stderr,
                )
                return json.dumps(safe_origins)
        return v

    # ── Rate Limiting ─────────────────────────────────────────
    RATE_LIMIT_LOGIN: str = "5/minute"
    RATE_LIMIT_DEFAULT: str = "60/minute"

    # ── Shift Defaults ────────────────────────────────────────
    MIN_REST_HOURS: int = 8

    # ── Email (SMTP) ──────────────────────────────────────────
    SMTP_HOST: str = ""
    SMTP_PORT: int = 587
    SMTP_USER: str = ""
    SMTP_PASSWORD: str = ""
    SMTP_FROM_EMAIL: str = ""
    SMTP_FROM_NAME: str = "EscalasPT"
    SMTP_USE_TLS: bool = True
    EMAIL_ENABLED: bool = False

    # ── Web Push (VAPID) ──────────────────────────────────────
    VAPID_PUBLIC_KEY: str = ""
    VAPID_PRIVATE_KEY: str = ""
    VAPID_CLAIMS_EMAIL: str = ""
    PUSH_ENABLED: bool = False

    # ── Validators ────────────────────────────────────────────

    @field_validator("JWT_SECRET_KEY")
    @classmethod
    def validate_jwt_secret(cls, v: str, info) -> str:
        # Allow weak secret in development; block in production
        env = info.data.get("APP_ENV", "development")
        if env != "development" and v in _INSECURE_JWT_DEFAULTS:
            print(
                "FATAL: JWT_SECRET_KEY is set to an insecure default. "
                "Set a strong secret via the JWT_SECRET_KEY environment variable.",
                file=sys.stderr,
            )
            sys.exit(1)
        if env == "development" and v in _INSECURE_JWT_DEFAULTS:
            import warnings
            warnings.warn(
                "JWT_SECRET_KEY is insecure. Set a strong value for production.",
                stacklevel=2,
            )
        return v

    @field_validator("TOTP_ENCRYPTION_KEY")
    @classmethod
    def validate_totp_key(cls, v: str, info) -> str:
        if v == "":
            return v  # TOTP disabled — fine until someone enables it
        # Validate that it's a valid Fernet key (44-char base64url)
        import base64
        try:
            decoded = base64.urlsafe_b64decode(v + "==")
            if len(decoded) != 32:
                raise ValueError("Fernet key must decode to exactly 32 bytes")
        except Exception as exc:
            raise ValueError(
                "TOTP_ENCRYPTION_KEY must be a valid 32-byte Fernet key "
                "(generate with: python -c \"from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())\")"
            ) from exc
        return v

@lru_cache
def get_settings() -> Settings:
    """Cached settings singleton."""
    return Settings()
