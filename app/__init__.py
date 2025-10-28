from flask import Flask, jsonify
from .extensions import db, migrate, login_manager, cors, jwt
from .config import Config
from .models import User


def create_app():
    app = Flask(__name__)
    app.config.from_object(Config)
    
    db.init_app(app)
    migrate.init_app(app, db)
    cors.init_app(app, origins=app.config["CORS_ORIGINS"], supports_credentials=True)
    jwt.init_app(app)

    def load_user(user_id):
        return User.query.get(user_id)

    def unauthorized():
        return jsonify(), 401

    from .blueprints.auth import bp as auth_bp

    app.register_blueprint(auth_bp, url_prefix="/auth")

    return app
