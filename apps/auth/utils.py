"""
Authentication utilities
"""
import re
from flask_jwt_extended import create_access_token, create_refresh_token, get_csrf_token
from flask import jsonify
from apps.auth.models import User, OauthType, AccountType


# Phone validation regex
PHONE_REGEX = re.compile(r"^0\d{1,2}-?\d{3,4}-?\d{4}$")


def is_valid_phone(phone: str) -> bool:
    """Validate Korean phone number format"""
    return bool(PHONE_REGEX.match(phone))


def token_provider(user_id, access_require=True, refresh_require=True, **kwargs):
    """
    Generate JWT tokens for user authentication
    
    Args:
        user_id: User ID to generate tokens for
        access_require: Whether to generate access token
        refresh_require: Whether to generate refresh token
        **kwargs: Additional claims to include in token
        
    Returns:
        JSON response with tokens and user data
    """
    user = User.query.filter(User.user_id == user_id).first_or_404()
    
    # Build additional claims
    additional_claims = {}
    if user.oauth_type != OauthType.NONE:
        additional_claims["oauth_type"] = user.oauth_type.value
    if user.account_type != AccountType.USER:
        additional_claims["account_type"] = user.account_type.value
    
    # Add custom claims
    for k, v in kwargs.items():
        additional_claims[k] = v
    
    # Generate tokens
    tokens = {}
    if access_require:
        access_token = create_access_token(
            identity=str(user_id), 
            additional_claims=additional_claims
        )
        tokens['access_token'] = access_token
        tokens['csrf_access_token'] = get_csrf_token(encoded_token=access_token)
    
    if refresh_require:
        refresh_token = create_refresh_token(
            identity=str(user_id),
            additional_claims=additional_claims
        )
        tokens['refresh_token'] = refresh_token
        tokens['csrf_refresh_token'] = get_csrf_token(encoded_token=refresh_token)
    
    # Build response
    response = jsonify({
        "message": "로그인 성공",
        **tokens,
        "user_data": user.to_dict(),
    })
    
    # Security headers
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["X-Frame-Options"] = "SAMEORIGIN"
    
    return response


def user_to_dict(user):
    """
    Convert User model to dictionary
    (Backward compatibility - use user.to_dict() instead)
    """
    return user.to_dict()
