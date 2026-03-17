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

    app.register_blueprint(main_bp)

    return app
