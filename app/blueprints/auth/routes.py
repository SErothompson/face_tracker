import json
import logging
from datetime import datetime, timedelta, timezone

from flask import (
    Blueprint,
    current_app,
    flash,
    redirect,
    render_template,
    request,
    session,
    url_for,
)
from flask_login import current_user, login_required, login_user, logout_user
from werkzeug.security import check_password_hash

from app.audit import log_event
from app.extensions import db
from app.models import User
from app.security import limiter
from app.utils import is_safe_url
from app.validators import validate_password_strength

auth_bp = Blueprint(
    "auth", __name__, url_prefix="/auth", template_folder="templates"
)

logger = logging.getLogger(__name__)


def _utcnow():
    """Return current UTC time as a naive datetime (compatible with SQLite)."""
    return datetime.now(timezone.utc).replace(tzinfo=None)


LOCKOUT_THRESHOLD = 5
LOCKOUT_DURATION = timedelta(minutes=15)


@auth_bp.route("/login", methods=["GET", "POST"])
@limiter.limit("5 per minute", methods=["POST"])
@limiter.limit("20 per hour", methods=["POST"])
def login():
    if current_user.is_authenticated:
        return redirect(url_for("main.dashboard"))

    if request.method == "POST":
        username = request.form.get("username", "").strip()
        password = request.form.get("password", "")
        remember = request.form.get("remember") == "on"

        if len(username) > 80 or len(password) > 128:
            flash("Invalid username or password.", "danger")
            return redirect(url_for("auth.login"))

        user = User.query.filter_by(username=username).first()

        # Check account lockout
        if user and user.locked_until and user.locked_until > _utcnow():
            log_event("login_locked", f"username={username}")
            flash(
                "Account temporarily locked due to too many failed attempts. "
                "Try again later.",
                "danger",
            )
            return redirect(url_for("auth.login"))

        if user and user.check_password(password):
            if not user.is_active:
                log_event("login_disabled", f"username={username}", user=user)
                flash("Your account has been disabled. Contact an admin.", "danger")
                return redirect(url_for("auth.login"))

            # Reset lockout counters
            user.failed_login_attempts = 0
            user.locked_until = None
            db.session.commit()

            # If 2FA enabled, redirect to verification
            if user.totp_enabled:
                session["pending_2fa_user_id"] = user.id
                session["pending_2fa_remember"] = remember
                return redirect(url_for("auth.verify_2fa"))

            login_user(user, remember=remember)
            log_event("login_success", f"username={username}", user=user)
            next_page = request.args.get("next")
            if not next_page or not is_safe_url(next_page):
                next_page = url_for("main.dashboard")
            return redirect(next_page)

        # Login failed
        if user:
            user.failed_login_attempts = (user.failed_login_attempts or 0) + 1
            user.last_failed_login = _utcnow()
            if user.failed_login_attempts >= LOCKOUT_THRESHOLD:
                user.locked_until = _utcnow() + LOCKOUT_DURATION
                log_event(
                    "account_locked",
                    f"username={username} attempts={user.failed_login_attempts}",
                    user=user,
                )
            db.session.commit()

        log_event("login_failed", f"username={username}")
        flash("Invalid username or password.", "danger")
        return redirect(url_for("auth.login"))

    return render_template("auth/login.html")


@auth_bp.route("/register", methods=["GET", "POST"])
@limiter.limit("3 per hour", methods=["POST"])
def register():
    if current_user.is_authenticated:
        return redirect(url_for("main.dashboard"))

    if not current_app.config.get("REGISTRATION_ENABLED", True):
        flash("Registration is currently disabled.", "info")
        return redirect(url_for("auth.login"))

    if request.method == "POST":
        username = request.form.get("username", "").strip()
        password = request.form.get("password", "")
        confirm_password = request.form.get("confirm_password", "")

        if not username:
            flash("Username is required.", "danger")
            return redirect(url_for("auth.register"))
        if len(username) < 3:
            flash("Username must be at least 3 characters.", "danger")
            return redirect(url_for("auth.register"))
        if len(username) > 80:
            flash("Username must be at most 80 characters.", "danger")
            return redirect(url_for("auth.register"))

        error = validate_password_strength(password)
        if error:
            flash(error, "danger")
            return redirect(url_for("auth.register"))

        if password != confirm_password:
            flash("Passwords do not match.", "danger")
            return redirect(url_for("auth.register"))
        if User.query.filter_by(username=username).first():
            flash("Username already taken.", "danger")
            return redirect(url_for("auth.register"))

        user = User(username=username, role="user")
        user.set_password(password)
        db.session.add(user)
        db.session.commit()

        login_user(user)
        log_event("registration", f"username={username}", user=user)
        flash("Account created successfully!", "success")
        return redirect(url_for("main.dashboard"))

    return render_template("auth/register.html")


@auth_bp.route("/logout", methods=["POST"])
@login_required
def logout():
    log_event("logout", f"username={current_user.username}")
    logout_user()
    flash("You have been logged out.", "info")
    return redirect(url_for("auth.login"))


@auth_bp.route("/profile")
@login_required
def profile():
    return render_template("auth/profile.html")


@auth_bp.route("/setup", methods=["GET", "POST"])
@limiter.limit("3 per hour", methods=["POST"])
def setup():
    if User.query.count() > 0:
        return redirect(url_for("auth.login"))

    if request.method == "POST":
        username = request.form.get("username", "").strip()
        password = request.form.get("password", "")
        confirm_password = request.form.get("confirm_password", "")

        if not username:
            flash("Username is required.", "danger")
            return redirect(url_for("auth.setup"))
        if len(username) < 3:
            flash("Username must be at least 3 characters.", "danger")
            return redirect(url_for("auth.setup"))
        if len(username) > 80:
            flash("Username must be at most 80 characters.", "danger")
            return redirect(url_for("auth.setup"))

        error = validate_password_strength(password)
        if error:
            flash(error, "danger")
            return redirect(url_for("auth.setup"))

        if password != confirm_password:
            flash("Passwords do not match.", "danger")
            return redirect(url_for("auth.setup"))

        user = User(username=username, role="admin")
        user.set_password(password)
        db.session.add(user)
        db.session.commit()

        log_event("setup_admin", f"username={username}", user=user)
        flash(
            f"Admin account '{username}' created. Please log in.", "success"
        )
        return redirect(url_for("auth.login"))

    return render_template("auth/setup.html")


@auth_bp.route("/2fa/verify", methods=["GET", "POST"])
@limiter.limit("5 per minute", methods=["POST"])
def verify_2fa():
    """Verify TOTP code during two-step login."""
    user_id = session.get("pending_2fa_user_id")
    if not user_id:
        return redirect(url_for("auth.login"))

    user = db.session.get(User, user_id)
    if not user:
        session.pop("pending_2fa_user_id", None)
        return redirect(url_for("auth.login"))

    if request.method == "POST":
        code = request.form.get("code", "").strip()

        import pyotp
        totp = pyotp.TOTP(user.totp_secret)
        if totp.verify(code, valid_window=1):
            remember = session.pop("pending_2fa_remember", False)
            session.pop("pending_2fa_user_id", None)
            login_user(user, remember=remember)
            log_event("login_2fa_success", f"username={user.username}", user=user)
            return redirect(url_for("main.dashboard"))

        # Check recovery codes
        if _check_recovery_code(user, code):
            remember = session.pop("pending_2fa_remember", False)
            session.pop("pending_2fa_user_id", None)
            login_user(user, remember=remember)
            log_event("login_2fa_recovery", f"username={user.username}", user=user)
            flash("Recovery code used. Consider generating new codes.", "warning")
            return redirect(url_for("main.dashboard"))

        log_event("login_2fa_failed", f"username={user.username}", user=user)
        flash("Invalid verification code.", "danger")
        return redirect(url_for("auth.verify_2fa"))

    return render_template("auth/2fa_verify.html")


def _check_recovery_code(user, code):
    """Check and consume a one-time recovery code."""
    if not user.recovery_codes_hash:
        return False
    try:
        codes = json.loads(user.recovery_codes_hash)
    except (json.JSONDecodeError, TypeError):
        return False
    for i, hashed_code in enumerate(codes):
        if check_password_hash(hashed_code, code):
            codes.pop(i)
            user.recovery_codes_hash = json.dumps(codes)
            db.session.commit()
            return True
    return False
