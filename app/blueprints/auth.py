from flask import Blueprint, request, jsonify
from ..extensions import db
from ..models import User
from email_validator import validate_email, EmailNotValidError
from flask_login import login_user, logout_user, login_required, current_user

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
