from flask import Flask, jsonify
from .extensions import db, migrate, login_manager, cors
from .config import Config
from .models import User


def create_app():
    app = Flask(__name__)
    app.config.from_object(Config)
    db.init_app(app)
    migrate.init_app(app, db)
    cors.init_app(app, origins=app.config["CORS_ORIGINS"], supports_credentials=True)
    login_manager.init_app(app)

    @login_manager.user_loader
    def load_user(user_id):
        return User.query.get(user_id)

    @login_manager.unauthorized_handler
    def unauthorized():
        return jsonify(), 401

    from blueprints.auth import bp as auth_bp

    app.register_blueprint(auth_bp, url_prefix="/auth")

    return app
