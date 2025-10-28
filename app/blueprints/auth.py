from flask import Blueprint, request, jsonify
from ..extensions import db
from ..models import User
from email_validator import validate_email, EmailNotValidError
from flask_jwt_extended import (
    create_access_token,
    create_refresh_token,
    jwt_required,
    get_jwt_identity,
    get_jwt,
)
import requests
from ..models.user import OauthType
from ..blacklist import add_to_blacklist

bp = Blueprint("auth", __name__)


@bp.route("/sign_up")
def sign_up():
    data = request.get_json() or {}
    username = data.get("username")
    password = data.get("password")
    email = data.get("email")
    nickname = data.get("nickname")
    address = data.get("address")

    if not username or not password or not email:
        return jsonify(), 400
    try:
        validate_email
    except EmailNotValidError as e:
        return jsonify({str(e)}), 400
    except Exception:
        return jsonify(), 400
    existing_user = User.query.filter(
        (User.username == username) | (User.email == email)
    ).first()
    if existing_user:
        return jsonify(), 409
    user = User(username=username, email=email, nickname=nickname, address=address)
    user.set_password(password)
    db.session.add(user)
    try:
        db.session.commit()
    except Exception:
        db.session.rollback()
        return jsonify(), 400
    return jsonify(), 200


@bp.route("/login", methods=["POST"])
def login():
    data = request.get_json() or {}
    username = data.get("username")
    password = data.get("password")

    if not username or not password:
        return jsonify({"message": "아이디와 비밀번호를 입력하세요"}), 400

    user = User.query.filter_by(username=username).first()
    if not user or not user.check_password(password):
        return jsonify({"message": "로그인 실패"}), 401

    access = create_access_token(identity=str(user.user_id))
    refresh = create_refresh_token(identity=str(user.user_id))
    return jsonify(access_token=access, refresh_token=refresh), 200


GOOGLE_TOKEN_INFO_URL = "https://oauth2.googleapis.com/tokeninfo"


# google 로그인
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

    access_token = create_access_token(identity=user.user_id)
    return jsonify({"message": "Google 로그인 완료", "access_token": access_token}), 200


# Kakao 로그인
@bp.route("/login/kakao", methods=["POST"])
def kakao_login():
    kakao_token = request.json.get("token")
    if not kakao_token:
        return jsonify({"error": "Token required"}), 400

    # 1️⃣ Kakao 사용자 정보 조회
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
    nickname = kakao_account.get("profile", {}).get("nickname", "KakaoUser")

    # 2️⃣ DB 조회
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

    # 3️⃣ JWT 발급
    access_token = create_access_token(identity=user.user_id)
    return jsonify({"message": "Kakao 로그인 완료", "access_token": access_token}), 200


# Naver 로그인
@bp.route("/login/naver", methods=["POST"])
def naver_login():
    naver_token = request.json.get("token")
    if not naver_token:
        return jsonify({"error": "Token required"}), 400

    # 1️⃣ Naver 사용자 정보 조회
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

    # 2️⃣ DB 조회
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

    # 3️⃣ JWT 발급
    access_token = create_access_token(identity=user.user_id)
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
    new_access_token = create_access_token(identity=current_user_id)

    return (
        jsonify(
            {
                "message": "새로운 Access Token 발급 완료",
                "access_token": new_access_token,
            }
        ),
        200,
    )
