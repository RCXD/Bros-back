from flask import Blueprint, request, jsonify
from ..extensions import db
from ..models import User
from email_validator import validate_email, EmailNotValidError
from datetime import datetime
from flask_jwt_extended import (
    create_access_token,
    create_refresh_token,
    jwt_required,
    get_jwt_identity,
    get_jwt,
)
from ..blacklist import add_to_blacklist

bp = Blueprint("auth", __name__)


@bp.route("/sign_up", methods=['POST'])
def sign_up():
    data = request.get_json() or {}
    username = data.get("username")
    password = data.get("password")
    email = data.get("email")
    nickname = data.get("nickname")
    address= data.get("address")

    if not username or not password or not email:
        return jsonify(), 400
    try:
        validate_email(email)
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
        return jsonify({'message' : '회원가입 실패'}), 400
    return jsonify({'message' : '회원가입 성공'}), 200


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


@bp.route("/logout", methods=["DELETE"])
@jwt_required()
def logout_access():
    jti = get_jwt()["jti"]
    add_to_blacklist(jti)
    return jsonify(msg="access token revoked"), 200


@bp.route("/logout_refresh", methods=["DELETE"])
@jwt_required(refresh=True)
def logout_refresh():
    jti = get_jwt()["jti"]
    add_to_blacklist(jti)
    return jsonify(msg="refresh token revoked"), 200

# 모든 유저 조건부 조회(쿼리 들어오면 들어온걸로 조회, 안들어오면 전체조회)
# 쿼리 = username, nickname
# 쿼리 없으면 전체조회
@jwt_required()
@bp.route("/users", methods=['GET'])
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
        result.append({
            "user_id": u.user_id,
            "username": u.username,
            "nickname": u.nickname,
            "email": u.email,
            "address": u.address,
            "profile_img": u.profile_img,
            "created_at": u.created_at.isoformat(),
            "last_login": u.last_login.isoformat() if u.last_login else None,
            "account_type": u.account_type.name,
            "oauth_type": u.oauth_type.name,
            "is_expired": u.is_expired,
            "follower_count": u.follower_count
        })
    return jsonify(result), 200

# id로 유저 조회(특정 회원 조회)
@jwt_required()
@bp.route("/users/<int:user_id>", methods=['GET'])
def get_user(user_id):
    user = User.query.get_or_404(user_id)
    return jsonify({
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
        "is_expired": user.is_expired,
        "follower_count": user.follower_count
    }), 200

# 내 정보 조회
@bp.route("/users/me", methods=["GET"])
@jwt_required()
def get_me():
    current_id = get_jwt_identity()
    user = User.query.get_or_404(current_id)
    return jsonify({
        "nickname": user.nickname,
        "email": user.email,
        "address": user.address,
        "profile_img": user.profile_img,
        "created_at": user.created_at.isoformat(),
        "last_login": user.last_login.isoformat() if user.last_login else None,
        "oauth_type": user.oauth_type.name,
        "follower_count": user.follower_count
    }), 200

# get요청 - 추후에 필요할수도 있는 것
# 검색 / 필터 확장, 팔로우 / 팔로워 관련 등