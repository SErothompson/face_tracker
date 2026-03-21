"""Audit logging for security-relevant events."""

import logging
from datetime import datetime, timezone

from flask import request
from flask_login import current_user

from app.extensions import db

audit_logger = logging.getLogger("audit")


def log_event(event_type, details=None, user=None):
    """Log a security-relevant event to both the audit logger and database."""
    u = user or (
        current_user
        if current_user and hasattr(current_user, "is_authenticated") and current_user.is_authenticated
        else None
    )
    username = u.username if u else "anonymous"
    user_id = u.id if u else None
    ip = request.remote_addr if request else "unknown"

    audit_logger.info(
        "[%s] user=%s ip=%s details=%s", event_type, username, ip, details
    )

    # Also persist to database
    try:
        from app.models import AuditLog
        entry = AuditLog(
            user_id=user_id,
            event_type=event_type,
            ip_address=ip,
            details=str(details) if details else "",
        )
        db.session.add(entry)
        db.session.commit()
    except Exception:
        # Don't let audit logging failures break the application
        db.session.rollback()
        audit_logger.exception("Failed to persist audit log entry")
