"""TOTP two-factor authentication setup and management routes."""

import io
import json
import secrets

import pyotp
import qrcode
from flask import (
    Blueprint,
    flash,
    redirect,
    render_template,
    request,
    send_file,
    url_for,
)
from flask_login import current_user, login_required
from werkzeug.security import generate_password_hash

from app.audit import log_event
from app.extensions import db
from app.security import limiter

totp_bp = Blueprint(
    "totp", __name__, url_prefix="/auth", template_folder="templates"
)


@totp_bp.route("/2fa/setup", methods=["GET", "POST"])
@login_required
def setup_2fa():
    """Set up TOTP two-factor authentication."""
    if current_user.totp_enabled:
        flash("Two-factor authentication is already enabled.", "info")
        return redirect(url_for("auth.profile"))

    if request.method == "POST":
        code = request.form.get("code", "").strip()
        secret = request.form.get("secret", "")

        if not secret:
            flash("Invalid setup state. Please try again.", "danger")
            return redirect(url_for("totp.setup_2fa"))

        totp = pyotp.TOTP(secret)
        if totp.verify(code, valid_window=1):
            # Generate recovery codes
            recovery_codes = [secrets.token_hex(4).upper() for _ in range(8)]
            hashed_codes = [generate_password_hash(c) for c in recovery_codes]

            current_user.totp_secret = secret
            current_user.totp_enabled = True
            current_user.recovery_codes_hash = json.dumps(hashed_codes)
            db.session.commit()

            log_event("2fa_enabled", f"username={current_user.username}")
            flash("Two-factor authentication has been enabled!", "success")
            return render_template(
                "auth/2fa_recovery.html", recovery_codes=recovery_codes
            )

        flash("Invalid verification code. Please try again.", "danger")
        return redirect(url_for("auth.setup_2fa"))

    # Generate new TOTP secret for setup
    secret = pyotp.random_base32()
    totp = pyotp.TOTP(secret)
    provisioning_uri = totp.provisioning_uri(
        name=current_user.username, issuer_name="Skin Health Tracker"
    )

    # Generate QR code as base64 data URI
    qr_img = qrcode.make(provisioning_uri)
    buf = io.BytesIO()
    qr_img.save(buf, format="PNG")
    buf.seek(0)
    import base64
    qr_data = base64.b64encode(buf.getvalue()).decode()

    return render_template(
        "auth/2fa_setup.html",
        secret=secret,
        qr_data=qr_data,
    )


@totp_bp.route("/2fa/disable", methods=["POST"])
@login_required
@limiter.limit("3 per hour")
def disable_2fa():
    """Disable TOTP two-factor authentication."""
    if not current_user.totp_enabled:
        flash("Two-factor authentication is not enabled.", "info")
        return redirect(url_for("auth.profile"))

    code = request.form.get("code", "").strip()
    totp = pyotp.TOTP(current_user.totp_secret)

    if not totp.verify(code, valid_window=1):
        flash("Invalid verification code.", "danger")
        return redirect(url_for("auth.profile"))

    current_user.totp_secret = None
    current_user.totp_enabled = False
    current_user.recovery_codes_hash = None
    db.session.commit()

    log_event("2fa_disabled", f"username={current_user.username}")
    flash("Two-factor authentication has been disabled.", "success")
    return redirect(url_for("auth.profile"))
