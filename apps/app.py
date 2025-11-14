"""
Flask Application Factory
Refactored architecture with modular blueprint structure
"""
from flask import Flask
from apps.config.common import config
from apps.config.server import db, migrate, cors, jwt
from apps.common.jwt_handlers import register_jwt_handlers
import os


def create_app(config_name='default'):
    """
    Application factory pattern
    
    Args:
        config_name: Configuration name (development, production, test)
        
    Returns:
        Flask application instance
    """
    app = Flask(__name__)
    
    # Load configuration
    app.config.from_object(config[config_name])
    
    # Static files configuration
    app.static_folder = "static"
    app.static_url_path = "/static"
    
    # Initialize extensions
    db.init_app(app)
    migrate.init_app(app, db)
    cors.init_app(app, origins=app.config['CORS_ORIGINS'])
    jwt.init_app(app)
    
    # Register JWT handlers
    register_jwt_handlers(jwt)
    
    # Register blueprints
    register_blueprints(app)
    
    # Create upload directories
    with app.app_context():
        create_directories(app)
    
    return app


def register_blueprints(app):
    """Register all application blueprints"""
    
    # Auth module
    from apps.auth.views import bp as auth_bp
    app.register_blueprint(auth_bp, url_prefix="/auth")
    
    # User module
    from apps.user.views import bp as user_bp
    app.register_blueprint(user_bp, url_prefix="/user")
    
    # Post module
    from apps.post.views import bp as post_bp
    app.register_blueprint(post_bp, url_prefix="/post")
    
    # Reply module
    from apps.reply.views import bp as reply_bp
    app.register_blueprint(reply_bp, url_prefix="/reply")
    
    # Feed module
    from apps.feed.views import bp as feed_bp
    app.register_blueprint(feed_bp, url_prefix="/feed")
    
    # Route module
    from apps.route.views import bp as route_bp
    app.register_blueprint(route_bp, url_prefix="/route")
    
    # Product module
    from apps.product.views import bp as product_bp
    app.register_blueprint(product_bp, url_prefix="/product")
    
    # Favorite module
    from apps.favorite.views import bp as favorite_bp
    app.register_blueprint(favorite_bp, url_prefix="/favorite")
    
    # Detector module
    from apps.detector.views import bp as detector_bp
    app.register_blueprint(detector_bp, url_prefix="/detector")
    
    # Security module
    from apps.security.views import bp as security_bp
    app.register_blueprint(security_bp, url_prefix="/security")
    
    # Admin module
    from apps.admin.views import bp as admin_bp
    app.register_blueprint(admin_bp, url_prefix="/admin")
    
    # Test module (if in development)
    if app.config.get('DEBUG'):
        from apps.test.views import bp as test_bp
        app.register_blueprint(test_bp, url_prefix="/test")


def create_directories(app):
    """Create necessary directories for file uploads"""
    directories = [
        os.path.join(app.root_path, 'static', 'profile_images'),
        os.path.join(app.root_path, 'static', 'post_images'),
        os.path.join(app.root_path, 'static', 'product_images'),
    ]
    
    for directory in directories:
        os.makedirs(directory, exist_ok=True)


if __name__ == '__main__':
    # Development server
    app = create_app('development')
    app.run(host='0.0.0.0', port=8000, debug=True)
