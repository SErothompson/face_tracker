import logging
import os
from logging.handlers import RotatingFileHandler

import click
from flask import Flask, jsonify, redirect, request as req, url_for
from flask_login import current_user

from .extensions import csrf, db, login_manager, migrate

CONFIG_MAP = {
    "development": "config.DevelopmentConfig",
    "testing": "config.TestingConfig",
    "production": "config.ProductionConfig",
}


def create_app(config_name=None):
    app = Flask(__name__)

    config_name = config_name or os.environ.get("FLASK_CONFIG", "development")
    app.config.from_object(CONFIG_MAP.get(config_name, CONFIG_MAP["development"]))

    # Run config-specific initialization (e.g. ProductionConfig validates SECRET_KEY)
    from config import ProductionConfig
    if config_name == "production":
        ProductionConfig.init_app(app)

    os.makedirs(app.config["UPLOAD_FOLDER"], exist_ok=True)
    os.makedirs(app.instance_path, exist_ok=True)

    # --- Core extensions ---
    db.init_app(app)
    migrate.init_app(app, db)
    login_manager.init_app(app)
    csrf.init_app(app)

    # --- Rate limiting ---
    from .security import limiter
    limiter.init_app(app)

    # --- Security headers (Talisman) ---
    if config_name != "testing":
        from flask_talisman import Talisman
        csp = {
            "default-src": "'self'",
            "script-src": [
                "'self'",
                "https://cdn.jsdelivr.net",
            ],
            "style-src": [
                "'self'",
                "https://cdn.jsdelivr.net",
                "'unsafe-inline'",
            ],
            "img-src": ["'self'", "data:"],
            "font-src": ["'self'", "https://cdn.jsdelivr.net"],
            "connect-src": "'self'",
        }
        Talisman(
            app,
            content_security_policy=csp,
            force_https=(config_name == "production"),
            session_cookie_secure=(config_name == "production"),
            session_cookie_samesite="Lax",
        )

    # --- Error handlers ---
    from .errors import register_error_handlers
    register_error_handlers(app)

    # --- Production logging ---
    if config_name == "production":
        os.makedirs("logs", exist_ok=True)
        file_handler = RotatingFileHandler(
            "logs/face_tracker.log", maxBytes=10 * 1024 * 1024, backupCount=5
        )
        file_handler.setLevel(logging.WARNING)
        file_handler.setFormatter(logging.Formatter(
            "%(asctime)s %(levelname)s: %(message)s [in %(pathname)s:%(lineno)d]"
        ))
        app.logger.addHandler(file_handler)

        audit_handler = RotatingFileHandler(
            "logs/audit.log", maxBytes=10 * 1024 * 1024, backupCount=10
        )
        audit_handler.setLevel(logging.INFO)
        audit_handler.setFormatter(logging.Formatter("%(asctime)s %(message)s"))
        logging.getLogger("audit").addHandler(audit_handler)

    # --- User loader ---
    from .models import User

    @login_manager.user_loader
    def load_user(user_id):
        return db.session.get(User, int(user_id))

    # --- Blueprints ---
    from .blueprints.main.routes import main_bp
    from .blueprints.sessions.routes import sessions_bp
    from .blueprints.analysis.routes import analysis_bp
    from .blueprints.regimen.routes import regimen_bp
    from .blueprints.api.routes import api_bp
    from .blueprints.comparison.routes import comparison_bp
    from .blueprints.search.routes import search_bp
    from .blueprints.reports.routes import reports_bp
    from .blueprints.auth.routes import auth_bp
    from .blueprints.admin.routes import admin_bp

    app.register_blueprint(main_bp)
    app.register_blueprint(sessions_bp)
    app.register_blueprint(analysis_bp)
    app.register_blueprint(regimen_bp)
    app.register_blueprint(api_bp)
    app.register_blueprint(comparison_bp)
    app.register_blueprint(search_bp)
    app.register_blueprint(reports_bp)
    app.register_blueprint(auth_bp)
    app.register_blueprint(admin_bp)

    # --- 2FA routes ---
    from .blueprints.auth.totp import totp_bp
    app.register_blueprint(totp_bp)

    # Seed regimen data on first run (non-testing)
    if config_name != "testing":
        with app.app_context():
            try:
                from .blueprints.regimen.defaults import seed_regimen
                seed_regimen()
            except Exception:
                pass

    # --- Before-request hooks ---

    @app.before_request
    def check_first_run():
        if req.endpoint and (
            req.endpoint.startswith(("auth.", "totp."))
            or req.endpoint == "static"
        ):
            return
        if User.query.count() == 0:
            return redirect(url_for("auth.setup"))

    @app.before_request
    def require_login():
        if req.endpoint and (
            req.endpoint.startswith(("auth.", "totp."))
            or req.endpoint == "static"
        ):
            return
        if not current_user.is_authenticated:
            if req.path.startswith("/api/"):
                return jsonify({"error": "Authentication required"}), 401
            return redirect(url_for("auth.login"))

    @app.before_request
    def enforce_2fa_for_privileged():
        """Force admin/developer users to set up 2FA before using the app."""
        if app.testing:
            return
        if not current_user.is_authenticated:
            return
        if not current_user.has_role("admin", "developer"):
            return
        if getattr(current_user, "totp_enabled", False):
            return
        allowed_endpoints = ("totp.setup_2fa", "auth.logout", "auth.profile", "static")
        if req.endpoint in allowed_endpoints or (req.endpoint and req.endpoint.startswith(("auth.", "totp."))):
            return
            return
        from flask import flash
        flash("Two-factor authentication is required for your role.", "warning")
        return redirect(url_for("totp.setup_2fa"))

    # --- CLI commands ---

    @app.cli.command("create-admin")
    @click.option("--username", prompt=True)
    @click.option(
        "--password", prompt=True, hide_input=True, confirmation_prompt=True
    )
    def create_admin_command(username, password):
        """Create an admin user."""
        from .validators import validate_password_strength
        error = validate_password_strength(password)
        if error:
            click.echo(f"Error: {error}")
            return
        if User.query.filter_by(username=username).first():
            click.echo(f"Error: User '{username}' already exists.")
            return
        user = User(username=username, role="admin")
        user.set_password(password)
        db.session.add(user)
        db.session.commit()
        click.echo(f"Admin user '{username}' created successfully.")

    return app
