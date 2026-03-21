"""Input validation utilities."""

import re


def validate_password_strength(password):
    """Return an error message if password is too weak, or None if acceptable."""
    if len(password) < 10:
        return "Password must be at least 10 characters."
    if not re.search(r"[A-Z]", password):
        return "Password must contain at least one uppercase letter."
    if not re.search(r"[a-z]", password):
        return "Password must contain at least one lowercase letter."
    if not re.search(r"[0-9]", password):
        return "Password must contain at least one digit."
    if not re.search(r'[!@#$%^&*(),.?":{}|<>\-_=+\[\]\\;\'~/`]', password):
        return "Password must contain at least one special character."
    return None
