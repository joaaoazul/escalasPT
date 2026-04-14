"""
Audit service — append-only audit log operations.
"""

from __future__ import annotations

import uuid
from typing import Any, Dict, Optional

from sqlalchemy.ext.asyncio import AsyncSession

from app.models.audit_log import AuditLog
from app.utils.logging import get_logger

logger = get_logger(__name__)


async def create_audit_log(
    db: AsyncSession,
    user_id: Optional[uuid.UUID],
    action: str,
    resource_type: str,
    resource_id: Optional[str] = None,
    old_data: Optional[Dict[str, Any]] = None,
    new_data: Optional[Dict[str, Any]] = None,
    ip_address: Optional[str] = None,
    user_agent: Optional[str] = None,
) -> AuditLog:
    """
    Create an audit log entry. This is append-only —
    the DB user has no UPDATE/DELETE permissions on audit_logs.
    """
    # Sanitize data — remove sensitive fields before logging
    # RGPD Art. 25: audit logs must not contain PII unnecessarily
    sensitive_keys = {
        "password", "password_hash", "totp_secret", "totp_secret_encrypted",
        "token", "refresh_token", "email", "full_name", "nip", "phone",
        "username",
    }

    def _sanitize(data: Optional[Dict]) -> Optional[Dict]:
        if data is None:
            return None
        return {k: "[REDACTED]" if k in sensitive_keys else v for k, v in data.items()}

    log_entry = AuditLog(
        id=uuid.uuid4(),
        user_id=user_id,
        action=action,
        resource_type=resource_type,
        resource_id=resource_id,
        old_data=_sanitize(old_data),
        new_data=_sanitize(new_data),
        ip_address=ip_address,
        user_agent=user_agent,
    )
    db.add(log_entry)
    # Don't flush here — let the transaction commit handle it
    logger.info(
        "Audit: action=%s resource=%s/%s user=%s",
        action, resource_type, resource_id, user_id,
    )
    return log_entry
