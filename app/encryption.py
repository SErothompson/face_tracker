"""Application-layer field encryption for sensitive data at rest."""

import os

from cryptography.fernet import Fernet


def _get_fernet():
    """Get a Fernet instance using the FIELD_ENCRYPTION_KEY env var."""
    key = os.environ.get("FIELD_ENCRYPTION_KEY")
    if not key:
        raise RuntimeError("FIELD_ENCRYPTION_KEY environment variable is required")
    return Fernet(key.encode())


def encrypt_field(value):
    """Encrypt a string value for database storage."""
    if not value:
        return value
    return _get_fernet().encrypt(value.encode()).decode()


def decrypt_field(value):
    """Decrypt a string value retrieved from the database."""
    if not value:
        return value
    try:
        return _get_fernet().decrypt(value.encode()).decode()
    except Exception:
        # If decryption fails (e.g. unencrypted legacy data), return as-is
        return value
