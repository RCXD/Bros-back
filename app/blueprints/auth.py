from flask import Blueprint, request, jsonify
from ..extensions import db
from ..models import User
from email_validator import validate_email, EmailNotValidError
from flask_login import login_user, logout_user, login_required, current_user
from datetime import datetime
import pytz

bp = Blueprint("auth", __name__)


@bp.route("/sign_up")
def sign_up():
    data = request.get_json()
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
    data = request.get_json()
    username = data.get("username")
    password = data.get("password")

    if not username or not password:
        return jsonify({"error": "아이디와 비밀번호를 입력하세요"}), 400

    user = User.query.filter_by(username=username).first()
    if not user or not user.check_password(password):
        return jsonify({"error": "로그인 실패"}), 401

    login_user(user)

    kst = pytz.timezone("Asia/Seoul")
    user.last_login = datetime.now(kst)

    try:
        db.session.commit()
    except Exception:
        db.session.rollback()
        return jsonify({"error": "로그인 시간 저장 실패"}), 500

    return jsonify({"message": "로그인 성공", "last_login": user.last_login.isoformat()}), 200

@bp.route("/logout", methods=["POST"])
@login_required
def logout():
    logout_user()
    return jsonify({"message": "로그아웃 성공"}), 200