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
def check_if_token_revoked(jwt_header: dict, jwt_payload: dict) -> bool:
    """Check whether a JWT has been revoked (added to the blacklist).

    Registered as the Flask-JWT-Extended blocklist loader.  Called
    automatically on every protected request.

    Args:
        jwt_header: Decoded JWT header dictionary.
        jwt_payload: Decoded JWT payload dictionary, which must contain
            the ``"jti"`` (JWT ID) claim.

    Returns:
        ``True`` if the token's JTI is present in ``BLACKLIST`` and the
        request should be rejected; ``False`` otherwise.
    """
    jti = jwt_payload["jti"]
    return jti in BLACKLIST
