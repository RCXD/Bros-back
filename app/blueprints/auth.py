from flask import Blueprint, request, jsonify
from ..extensions import db
from ..models import User, Post, PostLike
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


@bp.route("/sign_up")
def sign_up():
    data = request.get_json() or {}
    username = data.get("username")
    password = data.get("password")
    email = data.get("email")
    nickname = data.get("nickname")

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
    user = User(username=username, email=email, nickname=nickname)
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

    user.last_login = datetime.now()
    
    try:
        db.session.commit()
    except Exception:
        db.session.rollback()
        return jsonify({"message": "로그인 시간 저장 실패"}), 400

    access = create_access_token(identity=user.id)
    refresh = create_refresh_token(identity=user.id)
    return jsonify(access_token=access, refresh_token=refresh), 200

<<<<<<< Updated upstream
@bp.route("/logout", methods=["POST"])
@login_required
def logout():
    logout_user()
    return jsonify({"message": "로그아웃 성공"}), 200

@bp.route("/post/<int:post_id>/like", methods=["POST"])
@login_required
def toggle_like(post_id):
    post = Post.query.get_or_404(post_id)

    existing_like = PostLike.query.filter_by(
        post_id=post_id, user_id=current_user.user_id
    ).first()

    if existing_like:
        db.session.delete(existing_like)
        db.session.commit()
        return jsonify({"liked": False, "message": "좋아요 취소"}), 200
    else:
        new_like = PostLike(post_id=post_id, user_id=current_user.user_id)
        db.session.add(new_like)
        db.session.commit()
        return jsonify({"liked": True, "message": "좋아요 추가"}), 200
=======

@bp.route('/logout', methods=['DELETE'])
@jwt_required()
def logout_access():
    jti = get_jwt()['jti']
    add_to_blacklist(jti)
    return jsonify(msg='access token revoked'), 200

@bp.route('/logout_refresh', methods=['DELETE'])
@jwt_required(refresh=True)
def logout_refresh():
    jti = get_jwt()['jti']
    add_to_blacklist(jti)
    return jsonify(msg='refresh token revoked'), 200
>>>>>>> Stashed changes
