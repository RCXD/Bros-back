from flask import Blueprint, request, jsonify
from ..extensions import db
from ..models import User
from ..utils.image_utils import upload_profile  # ✅ 추가
from email_validator import validate_email, EmailNotValidError
from flask_jwt_extended import (
    create_access_token,
    create_refresh_token,
    jwt_required,
    get_jwt_identity,
    get_jwt,
)
from ..blueprints.jwt_handlers import register_jwt_handlers
import requests
from ..models.user import OauthType
from ..blacklist import add_to_blacklist

bp = Blueprint("auth", __name__)


# ✅ 일반 회원가입 시 프로필 이미지 처리 추가
@bp.route("/sign_up", methods=["POST"])
def sign_up():
    """
    일반 회원가입 (프로필 이미지 업로드 지원)
    form-data:
      - username
      - password
      - email
      - nickname
      - address
      - profile_img (선택, 파일)
    """
    username = request.form.get("username")
    password = request.form.get("password")
    email = request.form.get("email")
    nickname = request.form.get("nickname")
    address = request.form.get("address")
    file = request.files.get("profile_img")

    if not username or not password or not email:
        return jsonify({"error": "필수 항목 누락"}), 400

    try:
        validate_email(email)
    except EmailNotValidError as e:
        return jsonify({"error": str(e)}), 400

    existing_user = User.query.filter(
        (User.username == username) | (User.email == email)
    ).first()
    if existing_user:
        return jsonify({"error": "이미 존재하는 사용자"}), 409

    user = User(username=username, email=email, nickname=nickname, address=address)
    user.set_password(password)
    db.session.add(user)
    db.session.commit()  # ✅ 먼저 커밋해야 user.id 존재

    # ✅ 프로필 이미지 업로드 처리
    upload_profile(user, file=file)

    return jsonify({"message": "회원가입 완료"}), 200


# ✅ Google 로그인
@bp.route("/login/google", methods=["POST"])
def google_login():
    google_token = request.json.get("token")
    if not google_token:
        return jsonify({"error": "Token required"}), 400

    resp = requests.get(
        "https://oauth2.googleapis.com/tokeninfo", params={"id_token": google_token}
    )
    if resp.status_code != 200:
        return jsonify({"error": "Invalid Google token"}), 401

    data = resp.json()
    email = data.get("email")
    social_id = data.get("sub")
    name = data.get("name", "GoogleUser")
    picture_url = data.get("picture")  # ✅ Google 프로필 이미지 URL

    if not email or not social_id:
        return jsonify({"error": "Invalid token data"}), 401

    user = User.query.filter_by(username=social_id, oauth_type=OauthType.GOOGLE).first()
    if not user:
        user = User(
            username=social_id,
            email=email,
            nickname=name,
            oauth_type=OauthType.GOOGLE,
            address="",
            password_hash="",
        )
        db.session.add(user)
        db.session.commit()

        # ✅ Google 프로필 이미지 저장
        upload_profile(user, url=picture_url)

    access_token = create_access_token(identity=str(user.user_id))
    return jsonify({"message": "Google 로그인 완료", "access_token": access_token}), 200


# ✅ Kakao 로그인
@bp.route("/login/kakao", methods=["POST"])
def kakao_login():
    kakao_token = request.json.get("token")
    if not kakao_token:
        return jsonify({"error": "Token required"}), 400

    kakao_user_info = requests.get(
        "https://kapi.kakao.com/v2/user/me",
        headers={"Authorization": f"Bearer {kakao_token}"},
    )

    if kakao_user_info.status_code != 200:
        return jsonify({"error": "Invalid Kakao token"}), 401

    data = kakao_user_info.json()
    kakao_id = data.get("id")
    kakao_account = data.get("kakao_account", {})
    email = kakao_account.get("email", f"kakao_{kakao_id}@kakao.com")
    profile = kakao_account.get("profile", {})
    nickname = profile.get("nickname", "KakaoUser")
    image_url = profile.get("profile_image_url")  # ✅ 프로필 이미지 URL

    user = User.query.filter_by(
        username=str(kakao_id), oauth_type=OauthType.KAKAO
    ).first()
    if not user:
        user = User(
            username=str(kakao_id),
            email=email,
            nickname=nickname,
            oauth_type=OauthType.KAKAO,
            address="",
            password_hash="",
        )
        db.session.add(user)
        db.session.commit()

        # ✅ 카카오 프로필 이미지 업로드
        upload_profile(user, url=image_url)

    access_token = create_access_token(identity=str(user.user_id))
    return jsonify({"message": "Kakao 로그인 완료", "access_token": access_token}), 200


# ✅ Naver 로그인
@bp.route("/login/naver", methods=["POST"])
def naver_login():
    naver_token = request.json.get("token")
    if not naver_token:
        return jsonify({"error": "Token required"}), 400

    naver_user_info = requests.get(
        "https://openapi.naver.com/v1/nid/me",
        headers={"Authorization": f"Bearer {naver_token}"},
    )

    if naver_user_info.status_code != 200:
        return jsonify({"error": "Invalid Naver token"}), 401

    data = naver_user_info.json().get("response", {})
    naver_id = data.get("id")
    email = data.get("email", f"naver_{naver_id}@naver.com")
    nickname = data.get("nickname", "NaverUser")
    image_url = data.get("profile_image")  # ✅ 네이버 프로필 이미지 URL

    user = User.query.filter_by(
        username=str(naver_id), oauth_type=OauthType.NAVER
    ).first()
    if not user:
        user = User(
            username=str(naver_id),
            email=email,
            nickname=nickname,
            oauth_type=OauthType.NAVER,
            address="",
            password_hash="",
        )
        db.session.add(user)
        db.session.commit()

        # ✅ 네이버 프로필 이미지 업로드
        upload_profile(user, url=image_url)

    access_token = create_access_token(identity=str(user.user_id))
    return jsonify({"message": "Naver 로그인 완료", "access_token": access_token}), 200


@bp.route("/logout", methods=["DELETE"])
@jwt_required()
def logout_access():
    jti = get_jwt()["jti"]
    add_to_blacklist(jti)
    return jsonify(msg="액세스 토큰이 거부되었습니다"), 200


@bp.route("/logout_refresh", methods=["DELETE"])
@jwt_required(refresh=True)
def logout_refresh():
    jti = get_jwt()["jti"]
    add_to_blacklist(jti)
    return jsonify(msg="refresh token revoked"), 200


# ----------------------------
# Refresh Token으로 Access Token 재발급
# ----------------------------
@bp.route("/token/refresh", methods=["POST"])
@jwt_required(refresh=True)
def refresh_access_token():
    # 현재 refresh 토큰에서 사용자 ID 추출
    current_user_id = get_jwt_identity()
    new_access_token = create_access_token(identity=str(current_user_id))

    return (
        jsonify(
            {
                "message": "새로운 Access Token 발급 완료",
                "access_token": new_access_token,
            }
        ),
        200,
    )
