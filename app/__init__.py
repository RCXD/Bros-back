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

    @jwt.user_identity_loader
    def load_user(user_id):
        return User.query.get(user_id)

    @jwt.unauthorized_loader
    def expired_token_callback(jwt_header, jwt_payload):
        print("토큰만료", jwt_header, jwt_payload)
        return jsonify({"message": "로그인이 필요한 기능입니다"}), 401

    from .blueprints.auth import bp as auth_bp

    app.register_blueprint(auth_bp, url_prefix="/auth")

    return app
