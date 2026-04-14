"""
Security utilities: JWT, password hashing, TOTP, encryption.
Never log sensitive data from this module.
"""

from __future__ import annotations

import hashlib
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
    """Hash a plain-text password."""
    return pwd_context.hash(password)


def verify_password(plain_password: str, hashed_password: str) -> bool:
    """Verify a plain-text password against its hash."""
    return pwd_context.verify(plain_password, hashed_password)


# ── JWT Tokens ────────────────────────────────────────────


def create_access_token(
    user_id: str,
    role: str,
    station_id: Optional[str] = None,
    session_id: Optional[str] = None,
    extra_claims: Optional[Dict[str, Any]] = None,
) -> str:
    """Create a short-lived access token (15min default)."""
    now = datetime.now(timezone.utc)
    payload = {
        "sub": user_id,
        "role": role,
        "station_id": station_id,
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
    user_id: str,
    family_id: Optional[str] = None,
) -> tuple[str, str, str, datetime]:
    """
    Create a refresh token.
    Returns: (raw_token, token_hash, family_id, expires_at)
    """
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
    token_hash = hash_token(raw_token)
    return raw_token, token_hash, fid, expires_at


def decode_token(token: str) -> Dict[str, Any]:
    """
    Decode and validate a JWT token.
    Raises jwt.InvalidTokenError on failure.
    """
    return jwt.decode(
        token,
        settings.JWT_SECRET_KEY,
        algorithms=[settings.JWT_ALGORITHM],
    )


def hash_token(token: str) -> str:
    """SHA-256 hash of a token for secure storage."""
    return hashlib.sha256(token.encode()).hexdigest()


# ── TOTP ──────────────────────────────────────────────────


def generate_totp_secret() -> str:
    """Generate a new TOTP secret."""
    return pyotp.random_base32()


def get_totp_uri(secret: str, username: str) -> str:
    """Generate a TOTP provisioning URI for QR code display."""
    totp = pyotp.TOTP(secret)
    return totp.provisioning_uri(
        name=username,
        issuer_name=settings.TOTP_ISSUER_NAME,
    )


def verify_totp(secret: str, code: str) -> bool:
    """Verify a TOTP code with a 30-second window tolerance."""
    totp = pyotp.TOTP(secret)
    return totp.verify(code, valid_window=1)


# ── Field Encryption (AES-128-CBC via Fernet) ─────────────────

_fernet: Fernet | None = None


def _get_fernet() -> Fernet:
    """Lazy-init Fernet cipher from config. Generate key if not set."""
    global _fernet
    if _fernet is None:
        key = settings.TOTP_ENCRYPTION_KEY
        if not key:
            raise RuntimeError(
                "TOTP_ENCRYPTION_KEY not set. Generate with: "
                "python -c 'from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())'"
            )
        _fernet = Fernet(key.encode() if isinstance(key, str) else key)
    return _fernet


def encrypt_field(plaintext: str) -> str:
    """Encrypt a string field using Fernet (AES-128-CBC via Fernet spec)."""
    f = _get_fernet()
    return f.encrypt(plaintext.encode()).decode()


def decrypt_field(ciphertext: str) -> str:
    """Decrypt a Fernet-encrypted string field."""
    f = _get_fernet()
    return f.decrypt(ciphertext.encode()).decode()


# ── Password Strength (OWASP ASVS V2) ────────────────────

import re
import httpx


def validate_password_strength(password: str) -> list[str]:
    """
    Validate password meets OWASP ASVS Level 2 requirements.
    Returns a list of failure messages (empty = OK).
    """
    issues: list[str] = []
    if len(password) < 12:
        issues.append("Password must be at least 12 characters long")
    if not re.search(r'[A-Z]', password):
        issues.append("Password must contain at least one uppercase letter")
    if not re.search(r'[a-z]', password):
        issues.append("Password must contain at least one lowercase letter")
    if not re.search(r'\d', password):
        issues.append("Password must contain at least one digit")
    if not re.search(r'[!@#$%^&*(),.?":{}|<>]', password):
        issues.append("Password must contain at least one special character")
    return issues


async def check_password_hibp(password: str) -> bool:
    """
    Check if a password has been exposed in data breaches via
    HaveIBeenPwned's k-anonymity API (only first 5 chars of SHA-1 sent).
    Returns True if the password IS compromised.
    """
    sha1 = hashlib.sha1(password.encode("utf-8")).hexdigest().upper()  # nosec B324 — required by HIBP k-anonymity API
    prefix = sha1[:5]
    suffix = sha1[5:]
    try:
        async with httpx.AsyncClient(timeout=5.0) as client:
            resp = await client.get(f"https://api.pwnedpasswords.com/range/{prefix}")
            if resp.status_code == 200:
                for line in resp.text.splitlines():
                    hash_suffix, count = line.split(":")
                    if hash_suffix == suffix:
                        return True
    except Exception:
        # If HIBP is unreachable, don't block the user — fail open
        pass
    return False
