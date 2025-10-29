from flask import Flask, jsonify
from .extensions import db, migrate, cors, jwt
from .config import Config



def create_app():
    app = Flask(__name__)
    app.config.from_object(Config)

    db.init_app(app)
    migrate.init_app(app, db)
    cors.init_app(app, origins=app.config["CORS_ORIGINS"], supports_credentials=True)
    jwt.init_app(app)

 

    from .blueprints.auth import bp as auth_bp
    from .blueprints.post import bp as post_bp
    from .blueprints.reply import bp as reply_bp
    from .blueprints.mention import bp as mention_bp

    app.register_blueprint(auth_bp, url_prefix="/auth")
    app.register_blueprint(post_bp, url_prefix="/post")
    app.register_blueprint(reply_bp, url_prefix="/reply")
    app.register_blueprint(mention_bp, url_prefix="/mention")

    return app
