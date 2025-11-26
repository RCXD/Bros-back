"""
Authentication utilities
"""

import re
from flask_jwt_extended import create_access_token, create_refresh_token, get_csrf_token
from flask import jsonify
from apps.auth.models import User, OauthType, AccountType
from apps.user.reward_utils import get_medal_summary, get_user_league_info


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
            identity=str(user_id), additional_claims=additional_claims
        )
        tokens["access_token"] = access_token
        tokens["csrf_access_token"] = get_csrf_token(encoded_token=access_token)

    if refresh_require:
        refresh_token = create_refresh_token(
            identity=str(user_id), additional_claims=additional_claims
        )
        tokens["refresh_token"] = refresh_token
        tokens["csrf_refresh_token"] = get_csrf_token(encoded_token=refresh_token)

    # Build response
    response = jsonify(
        {
            "message": "로그인 성공",
            **tokens,
            "user_data": user.to_dict(),
        }
    )

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


def generate_login_response(user, db_session):
    """
    Generate standardized login response with tokens

    Args:
        user: User model instance
        db_session: Database session for commit

    Returns:
        tuple: (response_dict, status_code)
    """
    # Update last login time
    user.renew_login()
    db_session.commit()

    # 메달 정보 조회
    medal_info = get_medal_summary(user.user_id)

    # 리그 정보 조회 (미래 구현용)
    league_info = get_user_league_info(user.user_id)

    # Generate tokens with additional claims
    tokens = token_provider(
        user.user_id,
        additional_claims={
            "user_id": user.user_id,  # Deprecated 검토 중
            "username": user.username,  # Deprecated 검토 중
            "nickname": user.nickname,
            "email": user.email,
            "profile_img": user.profile_img,
            "account_type": user.account_type.name,
            "oauth_type": user.oauth_type.name,
            "points": user.points,
            # 메달 정보
            "medal": medal_info,
            # 리그 정보 (미래 구현용)
            "league": {
                "enabled": league_info.get("enabled", False),
                "id": league_info.get("league", {}).get("id", "unranked"),
            },
        },
    )

    return tokens.get_json(), 200


def find_or_create_oauth_user(
    username, email, nickname, oauth_type, db_session, profile_img_url=None
):
    """
    Find existing OAuth user or create new one

    Args:
        username: OAuth user ID (social_id)
        email: User email
        nickname: Display name
        oauth_type: OauthType enum value
        db_session: Database session
        profile_img_url: Optional profile image URL

    Returns:
        User: User model instance
    """
    user = User.query.filter_by(username=username, oauth_type=oauth_type).first()

    if not user:
        user = User(
            username=username,
            email=email,
            nickname=nickname,
            oauth_type=oauth_type,
            address="",
            password_hash="",
            profile_img="static/default_profile.jpg",
        )
        db_session.add(user)
        db_session.commit()

        # TODO: Download and save profile image if profile_img_url provided
        # This is optional and can be implemented later
        if profile_img_url:
            pass

    return user


def verify_oauth_token(provider, token):
    """
    Verify OAuth token and extract user information

    Args:
        provider: OAuth provider ("google", "kakao", "naver")
        token: OAuth token

    Returns:
        tuple: (oauth_type, username, email, nickname, profile_img_url) or (None, error_message)
    """
    import requests

    try:
        if provider == "google":
            GOOGLE_TOKEN_INFO_URL = "https://oauth2.googleapis.com/tokeninfo"
            resp = requests.get(GOOGLE_TOKEN_INFO_URL, params={"id_token": token})
            if resp.status_code != 200:
                return None, "유효하지 않은 토큰입니다"

            data = resp.json()
            email = data.get("email")
            social_id = data.get("sub")
            name = data.get("name", "GoogleUser")
            picture_url = data.get("picture")

            if not email or not social_id:
                return None, "토큰에서 필요한 정보를 가져올 수 없습니다"

            return OauthType.GOOGLE, social_id, email, name, picture_url

        elif provider == "kakao":
            KAKAO_USER_INFO_URL = "https://kapi.kakao.com/v2/user/me"
            headers = {"Authorization": f"Bearer {token}"}
            resp = requests.get(KAKAO_USER_INFO_URL, headers=headers)

            if resp.status_code != 200:
                return None, "유효하지 않은 토큰입니다"

            data = resp.json()
            kakao_id = data.get("id")
            kakao_account = data.get("kakao_account", {})
            email = kakao_account.get("email", f"kakao_{kakao_id}@kakao.com")
            profile = kakao_account.get("profile", {})
            nickname = profile.get("nickname", "KakaoUser")
            image_url = profile.get("profile_image_url")

            if not kakao_id:
                return None, "토큰에서 필요한 정보를 가져올 수 없습니다"

            return OauthType.KAKAO, str(kakao_id), email, nickname, image_url

        elif provider == "naver":
            NAVER_USER_INFO_URL = "https://openapi.naver.com/v1/nid/me"
            headers = {"Authorization": f"Bearer {token}"}
            resp = requests.get(NAVER_USER_INFO_URL, headers=headers)

            if resp.status_code != 200:
                return None, "유효하지 않은 토큰입니다"

            data = resp.json().get("response", {})
            naver_id = data.get("id")
            email = data.get("email", f"naver_{naver_id}@naver.com")
            nickname = data.get("nickname", "NaverUser")
            image_url = data.get("profile_image")

            if not naver_id:
                return None, "토큰에서 필요한 정보를 가져올 수 없습니다"

            return OauthType.NAVER, str(naver_id), email, nickname, image_url

        else:
            return None, f"지원하지 않는 OAuth 제공자입니다: {provider}"

    except Exception as e:
        return None, f"OAuth 검증 실패: {str(e)}"
