"""
Flask extensions initialization
Shared across all modules
"""
from flask_sqlalchemy import SQLAlchemy
from flask_migrate import Migrate
from flask_cors import CORS
from flask_jwt_extended import JWTManager

# Initialize extensions
db = SQLAlchemy()
migrate = Migrate()
cors = CORS()
jwt = JWTManager()

# JWT Blacklist (for token revocation)
BLACKLIST = set()


@jwt.token_in_blocklist_loader
def check_if_token_revoked(jwt_header, jwt_payload):
    """Check if token is in blacklist"""
    jti = jwt_payload["jti"]
    return jti in BLACKLIST
