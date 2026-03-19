import os

import click
from flask import Flask, jsonify, redirect, request as req, url_for
from flask_login import current_user

from .extensions import db, login_manager, migrate


def create_app(config_name=None):
    app = Flask(__name__)

    if config_name == "testing":
        app.config.from_object("config.TestingConfig")
    else:
        app.config.from_object("config.DevelopmentConfig")

    os.makedirs(app.config["UPLOAD_FOLDER"], exist_ok=True)
    os.makedirs(app.instance_path, exist_ok=True)

    db.init_app(app)
    migrate.init_app(app, db)
    login_manager.init_app(app)

    from .models import User

    @login_manager.user_loader
    def load_user(user_id):
        return db.session.get(User, int(user_id))

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

    # Seed regimen data on first run (non-testing)
    if config_name != "testing":
        with app.app_context():
            try:
                from .blueprints.regimen.defaults import seed_regimen
                seed_regimen()
            except Exception:
                pass

    @app.before_request
    def check_first_run():
        if req.endpoint and (
            req.endpoint.startswith("auth.")
            or req.endpoint == "static"
        ):
            return
        if User.query.count() == 0:
            return redirect(url_for("auth.setup"))

    @app.before_request
    def require_login():
        # Allow unauthenticated access to auth routes and static files
        if req.endpoint and (
            req.endpoint.startswith("auth.")
            or req.endpoint == "static"
        ):
            return
        if not current_user.is_authenticated:
            if req.path.startswith("/api/"):
                return jsonify({"error": "Authentication required"}), 401
            return redirect(url_for("auth.login"))

    @app.cli.command("create-admin")
    @click.option("--username", prompt=True)
    @click.option(
        "--password", prompt=True, hide_input=True, confirmation_prompt=True
    )
    def create_admin_command(username, password):
        """Create an admin user."""
        if len(password) < 8:
            click.echo("Error: Password must be at least 8 characters.")
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
