import os

from flask import Flask

from .extensions import db, migrate


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

    from .blueprints.main.routes import main_bp
    from .blueprints.sessions.routes import sessions_bp
    from .blueprints.analysis.routes import analysis_bp
    from .blueprints.regimen.routes import regimen_bp
    from .blueprints.api.routes import api_bp
    from .blueprints.comparison.routes import comparison_bp

    app.register_blueprint(main_bp)
    app.register_blueprint(sessions_bp)
    app.register_blueprint(analysis_bp)
    app.register_blueprint(regimen_bp)
    app.register_blueprint(api_bp)
    app.register_blueprint(comparison_bp)

    # Seed regimen data on first run (non-testing)
    if config_name != "testing":
        with app.app_context():
            from .blueprints.regimen.defaults import seed_regimen
            seed_regimen()

    return app
