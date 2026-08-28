"""
Security utilities: password hashing, JWT, TOTP, field encryption.
Never log anything this module handles.
"""

from __future__ import annotations

import hashlib
import re
import uuid
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, Optional

import jwt
import pyotp
from cryptography.fernet import Fernet
from passlib.context import CryptContext

from app.config import get_settings

settings = get_settings()

# ── Password Hashing ─────────────────────────────────────

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto", bcrypt__rounds=12)


def hash_password(password: str) -> str:
    return pwd_context.hash(password)


def verify_password(plain_password: str, hashed_password: str) -> bool:
    return pwd_context.verify(plain_password, hashed_password)


# ── JWT ───────────────────────────────────────────────────


def create_access_token(
    user_id: str,
    role: str,
    equipa_id: Optional[str] = None,
    session_id: Optional[str] = None,
    extra_claims: Optional[Dict[str, Any]] = None,
) -> str:
    now = datetime.now(timezone.utc)
    payload = {
        "sub": user_id,
        "role": role,
        "equipa_id": equipa_id,
        "sid": session_id,
        "type": "access",
        "iat": now,
        "exp": now + timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES),
        "jti": str(uuid.uuid4()),
    }
    if extra_claims:
        payload.update(extra_claims)
    return jwt.encode(payload, settings.JWT_SECRET_KEY, algorithm=settings.JWT_ALGORITHM)


def create_refresh_token(
    user_id: str, family_id: Optional[str] = None
) -> tuple[str, str, str, datetime]:
    """Returns (raw_token, token_hash, family_id, expires_at)."""
    now = datetime.now(timezone.utc)
    fid = family_id or str(uuid.uuid4())
    expires_at = now + timedelta(days=settings.REFRESH_TOKEN_EXPIRE_DAYS)
    payload = {
        "sub": user_id,
        "type": "refresh",
        "family": fid,
        "iat": now,
        "exp": expires_at,
        "jti": str(uuid.uuid4()),
    }
    raw_token = jwt.encode(payload, settings.JWT_SECRET_KEY, algorithm=settings.JWT_ALGORITHM)
    return raw_token, hash_token(raw_token), fid, expires_at


def decode_token(token: str) -> Dict[str, Any]:
    """Decode and validate a JWT. Raises jwt.InvalidTokenError on failure."""
    return jwt.decode(token, settings.JWT_SECRET_KEY, algorithms=[settings.JWT_ALGORITHM])


def hash_token(token: str) -> str:
    return hashlib.sha256(token.encode()).hexdigest()


# ── TOTP ──────────────────────────────────────────────────


def generate_totp_secret() -> str:
    return pyotp.random_base32()


def get_totp_uri(secret: str, username: str) -> str:
    return pyotp.TOTP(secret).provisioning_uri(
        name=username, issuer_name=settings.TOTP_ISSUER_NAME
    )


def verify_totp(secret: str, code: str) -> bool:
    return pyotp.TOTP(secret).verify(code, valid_window=1)


# ── TOTP secret encryption at rest ────────────────────────

_fernet: Fernet | None = None


def _get_fernet() -> Fernet:
    global _fernet
    if _fernet is None:
        key = settings.TOTP_ENCRYPTION_KEY
        if not key:
            raise RuntimeError(
                "TOTP_ENCRYPTION_KEY not set. Generate with: python -c "
                "'from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())'"
            )
        _fernet = Fernet(key.encode() if isinstance(key, str) else key)
    return _fernet


def encrypt_field(plaintext: str) -> str:
    return _get_fernet().encrypt(plaintext.encode()).decode()


def decrypt_field(ciphertext: str) -> str:
    return _get_fernet().decrypt(ciphertext.encode()).decode()


# ── Password strength (OWASP ASVS V2) ─────────────────────


def validate_password_strength(password: str) -> list[str]:
    """Return a list of failures (empty means the password is acceptable)."""
    issues: list[str] = []
    if len(password) < 12:
        issues.append("A palavra-passe tem de ter pelo menos 12 caracteres")
    if not re.search(r"[A-Z]", password):
        issues.append("Tem de conter pelo menos uma maiúscula")
    if not re.search(r"[a-z]", password):
        issues.append("Tem de conter pelo menos uma minúscula")
    if not re.search(r"\d", password):
        issues.append("Tem de conter pelo menos um algarismo")
    if not re.search(r'[!@#$%^&*(),.?":{}|<>]', password):
        issues.append("Tem de conter pelo menos um símbolo")
    return issues
