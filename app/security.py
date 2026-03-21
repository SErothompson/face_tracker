"""Centralized security utilities: rate limiting, IP allowlisting."""

import ipaddress
from functools import wraps

from flask import abort, current_app, request
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address

limiter = Limiter(
    key_func=get_remote_address,
    default_limits=["200 per day", "50 per hour"],
    storage_uri="memory://",
)


def check_admin_ip_allowed():
    """Check if the requesting IP is in the admin allowlist.

    Returns True if no allowlist configured or if client IP matches.
    """
    raw = current_app.config.get("ADMIN_ALLOWED_IPS", "")
    if not raw or not raw.strip():
        return True
    allowed_entries = [e.strip() for e in raw.split(",") if e.strip()]
    if not allowed_entries:
        return True
    client_ip = request.remote_addr
    for entry in allowed_entries:
        try:
            if ipaddress.ip_address(client_ip) in ipaddress.ip_network(
                entry, strict=False
            ):
                return True
        except ValueError:
            continue
    return False
