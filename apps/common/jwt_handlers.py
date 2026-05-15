"""JWT event handlers and callbacks for Flask-JWT-Extended."""

from flask import jsonify
from apps.config.server import BLACKLIST


def register_jwt_handlers(jwt_manager) -> None:
    """Register all JWT event callbacks on *jwt_manager*.

    Registers the following callbacks:

    * ``user_identity_loader`` – extracts a ``user_id`` from a
      :class:`~apps.auth.models.User` instance.
    * ``user_lookup_loader`` – loads a ``User`` from the JWT ``sub``
      claim.
    * ``unauthorized_loader`` – returns 401 when no token is provided.
    * ``invalid_token_loader`` – returns 401 for malformed tokens.
    * ``expired_token_loader`` – returns 401 for expired tokens.
    * ``revoked_token_loader`` – returns 401 for revoked/logged-out
      tokens.
    * ``token_in_blocklist_loader`` – checks the in-memory ``BLACKLIST``
      set.

    Args:
        jwt_manager: The :class:`flask_jwt_extended.JWTManager` instance
            to register callbacks on.
    """

    @jwt_manager.user_identity_loader
    def user_identity_lookup(user):
        """Return the identity value (``user_id``) to embed in the JWT.

        Args:
            user: A :class:`~apps.auth.models.User` instance or a raw
                identity value.

        Returns:
            The ``user_id`` attribute if *user* is a ``User`` model
            instance, otherwise *user* unchanged.
        """
        from apps.auth.models import User

        return user.user_id if isinstance(user, User) else user

    @jwt_manager.user_lookup_loader
    def user_lookup_callback(_jwt_header, jwt_data):
        """Load the ``User`` object corresponding to the JWT identity.

        Args:
            _jwt_header: The decoded JWT header (unused).
            jwt_data: The decoded JWT payload; ``jwt_data["sub"]`` holds
                the ``user_id``.

        Returns:
            The matching :class:`~apps.auth.models.User` instance, or
            ``None`` if not found.
        """
        from apps.auth.models import User

        identity = jwt_data["sub"]
        return User.query.get(identity)

    @jwt_manager.unauthorized_loader
    def unauthorized_callback(err):
        """Return a 401 response when no authorization token is present.

        Args:
            err: Error message string from Flask-JWT-Extended.

        Returns:
            JSON 401 response asking the user to log in again.
        """
        return jsonify({"message": "다시 로그인해주세요."}), 401

    @jwt_manager.invalid_token_loader
    def invalid_token_callback(err):
        """Return a 401 response for an invalid or malformed token.

        Args:
            err: Error message string from Flask-JWT-Extended.

        Returns:
            JSON 401 response.
        """
        return (
            jsonify({"message": "유효하지 않은 토큰입니다. 다시 로그인해주세요."}),
            401,
        )

    @jwt_manager.expired_token_loader
    def expired_token_callback(jwt_header, jwt_payload):
        """Return a 401 response when the JWT has expired.

        Args:
            jwt_header: The decoded JWT header.
            jwt_payload: The decoded JWT payload.

        Returns:
            JSON 401 response.
        """
        return jsonify({"message": "토큰이 만료되었습니다. 다시 로그인해주세요."}), 401

    @jwt_manager.revoked_token_loader
    def revoked_token_callback(jwt_header, jwt_payload):
        """Return a 401 response when the JWT has been revoked or logged out.

        Args:
            jwt_header: The decoded JWT header.
            jwt_payload: The decoded JWT payload.

        Returns:
            JSON 401 response.
        """
        return (
            jsonify(
                {
                    "message": "이미 만료되었거나 로그아웃된 토큰입니다. 다시 로그인해주세요."
                }
            ),
            401,
        )

    @jwt_manager.token_in_blocklist_loader
    def check_if_token_in_blocklist(jwt_header, jwt_payload):
        """Check whether the JWT's ``jti`` is in the revocation blocklist.

        Args:
            jwt_header: The decoded JWT header (unused).
            jwt_payload: The decoded JWT payload; ``jwt_payload["jti"]``
                is the unique token identifier.

        Returns:
            ``True`` if the token has been revoked, ``False`` otherwise.
        """
        jti = jwt_payload["jti"]
        return jti in BLACKLIST
