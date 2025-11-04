from flask import Flask, jsonify
from .extensions import db, migrate, cors, jwt
from .config import Config
from .jwt_handlers import register_jwt_handlers


def create_app():
    app = Flask(__name__)
    app.config.from_object(Config)

    db.init_app(app)
    migrate.init_app(app, db)
    cors.init_app(
        app,
        origins=Config.CORS_ORIGINS,
    )
    # cors.init_app(app,origins="*")
    jwt.init_app(app)
    register_jwt_handlers(jwt)

    from .blueprints.auth import bp as auth_bp
    from .blueprints.post import bp as post_bp
    from .blueprints.reply import bp as reply_bp
    from .blueprints.mention import bp as mention_bp
    from .blueprints.report import bp as report_bp
    from .blueprints.post_like import bp as post_like_bp
    from .blueprints.reply_like import bp as reply_like_bp
    from .blueprints.follow import bp as follow_bp
    from .blueprints.friend import bp as friend_bp

    app.register_blueprint(auth_bp, url_prefix="/auth")
    app.register_blueprint(post_bp, url_prefix="/post")
    app.register_blueprint(reply_bp, url_prefix="/reply")
    app.register_blueprint(mention_bp, url_prefix="/mention")
    app.register_blueprint(report_bp, url_prefix="/report")
    app.register_blueprint(post_like_bp, url_prefix="/post_like")
    app.register_blueprint(reply_like_bp, url_prefix="/reply_like")
    app.register_blueprint(follow_bp, url_prefix="/follow")
    app.register_blueprint(friend_bp, url_prefix="/friend")

    return app
