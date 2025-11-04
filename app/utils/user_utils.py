from flask_jwt_extended import create_access_token, create_refresh_token, get_csrf_token
from flask import jsonify
from ..models import User
import re


def token_provider(user_id, **kwargs):
    additional_claims = {}
    for k, v in kwargs.items():
        additional_claims[k] = v
    access = create_access_token(identity=str(user_id), additional_claims=additional_claims)
    refresh = create_refresh_token(identity=str(user_id), additional_claims=additional_claims)

    user = User.query.filter(User.user_id == user_id).first_or_404()
    response = jsonify(
        {
            "message": "로그인 성공",
            "csrf_access_token": get_csrf_token(access),
            "csrf_refresh_token": get_csrf_token(refresh),
            "access_token": access,
            "refresh_token": refresh,
            "user_data": user_to_dict(user),
        }
    )

    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["X-Frame-Options"] = "SAMEORIGIN"

    return response


def user_to_dict(user):
    return {
        "user_id": user.user_id,
        "username": user.username,
        "nickname": user.nickname,
        "email": user.email,
        "address": user.address,
        "profile_img": user.profile_img,
        "created_at": user.created_at.isoformat(),
        "last_login": user.last_login.isoformat() if user.last_login else None,
        "account_type": user.account_type.name,
        "oauth_type": user.oauth_type.name,
        "follower_count": user.follower_count,
    }


PHONE_REGEX = re.compile(r"^0\d{1,2}-?\d{3,4}-?\d{4}$")


def is_valid_phone(phone: str) -> bool:
    return bool(PHONE_REGEX.match(phone))
