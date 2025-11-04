from flask import Blueprint, request, jsonify
from ..extensions import db
from ..models import User
from ..utils.image_utils import upload_profile
from email_validator import validate_email, EmailNotValidError
from flask_jwt_extended import jwt_required, create_access_token, get_current_user
import requests
from ..models.user import OauthType
from ..utils.user_utils import token_provider


bp = Blueprint("auth", __name__)


#  일반 회원가입 시 프로필 이미지 처리 추가
@bp.route("/sign_up", methods=["POST"])
def sign_up():
    """
    일반 회원가입 (프로필 이미지 업로드 지원)
      - username
      - password
      - email
      - nickname
      - address
      - profile_img (선택, 파일)
    """
    data = request.get_json()  #  form-data로 받음

    username = data.get("username")
    password = data.get("password")
    email = data.get("email")
    nickname = data.get("nickname")
    address = data.get("address")
    phone = data.get("phone")

    if not username or not password or not email:
        return jsonify({"message": "필수 항목 누락되었습니다."}), 400

    try:
        validate_email(email)
    except EmailNotValidError as e:
        return jsonify({"message": "이메일 형식이 잘못되었습니다."}), 400

    existing_user = User.query.filter((User.username == username)).first()
    if existing_user:
        return jsonify({"message": "이미 존재하는 아이디입니다."}), 409

    existing_email = User.query.filter((User.email == email)).first()
    if existing_email:
        return jsonify({"message": "이미 사용중인 이메일입니다."}), 409

    if not nickname:
        nickname = username

    user = User(
        username=username, email=email, nickname=nickname, address=address, phone=phone
    )
    user.set_password(password)
    db.session.add(user)

    try:
        db.session.commit()  #  먼저 커밋해야 user.id 존재
    except Exception:
        db.session.rollback()
        return jsonify({"message": "회원가입에 실패했습니다."}), 400
    return jsonify({"message": "회원가입에 완료했습니다."}), 200


@bp.route("/login", methods=["POST"])
def login():
    data = request.get_json() or {}
    username = data.get("username")
    password = data.get("password")

    if not username or not password:
        return jsonify({"message": "아이디와 비밀번호를 입력하세요"}), 400

    user = User.query.filter_by(username=username).first_or_404()
    try:
        user.follower_count = User.calculate_follower(user)
        db.session.commit()
    except:
        db.session.rollback()
    if not user or not user.check_password(password):
        return jsonify({"message": "로그인 실패"}), 401

    return token_provider(user.user_id)


GOOGLE_TOKEN_INFO_URL = "https://oauth2.googleapis.com/tokeninfo"


#  Google 로그인
@bp.route("/login/google", methods=["POST"])
def google_login():
    google_token = request.json.get("token")
    if not google_token:
        return jsonify({"message": "Token required"}), 400

    resp = requests.get(GOOGLE_TOKEN_INFO_URL, params={"id_token": google_token})
    if resp.status_code != 200:
        return jsonify({"message": "잘못된 요청입니다."}), 401

    data = resp.json()
    email = data.get("email")
    social_id = data.get("sub")
    name = data.get("name", "GoogleUser")
    picture_url = data.get("picture")  #  Google 프로필 이미지 URL

    if not email or not social_id:
        return jsonify({"message": "잘못된 요청입니다."}), 401

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
        try:
            db.session.commit()
        except:
            db.session.rollback()
        #  Google 프로필 이미지 저장
        upload_profile(user, url=picture_url)

    return token_provider(user.user_id)


#  Kakao 로그인
@bp.route("/login/kakao", methods=["POST"])
def kakao_login():
    kakao_token = request.json.get("token")
    if not kakao_token:
        return jsonify({"message": "잘못된 요청입니다."}), 400

    kakao_user_info = requests.get(
        "https://kapi.kakao.com/v2/user/me",
        headers={"Authorization": f"Bearer {kakao_token}"},
    )

    if kakao_user_info.status_code != 200:
        return jsonify({"message": "잘못된 요청입니다."}), 401

    data = kakao_user_info.json()
    kakao_id = data.get("id")
    kakao_account = data.get("kakao_account", {})
    email = kakao_account.get("email", f"kakao_{kakao_id}@kakao.com")
    profile = kakao_account.get("profile", {})
    nickname = profile.get("nickname", "KakaoUser")
    image_url = profile.get("profile_image_url")  #  프로필 이미지 URL

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

        #  카카오 프로필 이미지 업로드
        upload_profile(user, url=image_url)

    return token_provider(user.user_id)


#  Naver 로그인
@bp.route("/login/naver", methods=["POST"])
def naver_login():
    naver_token = request.json.get("token")
    if not naver_token:
        return jsonify({"message": "잘못된 요청입니다."}), 400

    naver_user_info = requests.get(
        "https://openapi.naver.com/v1/nid/me",
        headers={"Authorization": f"Bearer {naver_token}"},
    )

    if naver_user_info.status_code != 200:
        return jsonify({"message": "잘못된 요청입니다."}), 401

    data = naver_user_info.json().get("response", {})
    naver_id = data.get("id")
    email = data.get("email", f"naver_{naver_id}@naver.com")
    nickname = data.get("nickname", "NaverUser")
    image_url = data.get("profile_image")  #  네이버 프로필 이미지 URL

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

        #  네이버 프로필 이미지 업로드
        upload_profile(user, url=image_url)

    return token_provider(user.user_id)


@bp.route("/logout", methods=["DELETE"])
@jwt_required()
def logout_access():
    response = jsonify({"message": "로그아웃 되었습니다."}), 200
    return response


# 모든 유저 조건부 조회(쿼리 들어오면 들어온걸로 조회, 안들어오면 전체조회)
# 쿼리 = username, nickname
# 쿼리 없으면 전체조회
@bp.route("/users", methods=["GET"])
@jwt_required()
def get_users():

    filters = {}
    for key, value in request.args.items():
        if value:
            filters[key] = value

    query = User.query

    for key, value in filters.items():
        column = getattr(User, key, None)
        if column is not None:
            query = query.filter(column.ilike(f"%{value}%"))

    users = query.all()

    result = []

    for u in users:
        result.append(
            {
                "user_id": u.user_id,
                "nickname": u.nickname,
                "email": u.email,
                "address": u.address,
                "profile_img": u.profile_img,
                "created_at": u.created_at.isoformat(),
                "follower_count": u.follower_count,
            }
        )
    return jsonify(result), 200


# id로 유저 조회(특정 회원 조회)
@bp.route("/users/<int:user_id>", methods=["GET"])
@jwt_required()
def get_user(user_id):
    user = User.query.get_or_404(user_id)
    user_profile = user.profile_img
    return (
        jsonify(
            {
                "user_id": user.user_id,
                "nickname": user.nickname,
                "email": user.email,
                "address": user.address,
                "profile_img": user.profile_img,
                "created_at": user.created_at.isoformat(),
                "follower_count": user.follower_count,
            }
        ),
        200,
    )


# 내 정보 조회
@bp.route("/me", methods=["GET"])
@jwt_required()
def get_info():
    current_user=get_current_user()
    if not current_user:
        return jsonify({"error": "사용자를 찾을 수 없습니다."}), 404
    User.calculate_follower(current_user)
    db.session.add(current_user)
    db.session.commit()
    user_info = {
        "user_id": current_user.user_id,
        "username": current_user.username,
        "email": current_user.email,
        "nickname": current_user.nickname,
        "address": current_user.address,
        "profile_img": current_user.profile_img,
        "created_at": current_user.created_at,
        "last_login": current_user.last_login,
        "follower_count": current_user.follower_count,
    }
    return jsonify(user_info), 200
