from flask import Blueprint, request, jsonify
from ..models import Post
from ..extensions import db

bp = Blueprint("post", __name__)


@bp.route("/write")
def write():
    data = request.get_json() or {}
    post = Post(
        user_id=data.get("user_id"),
        category_id=data.get("category_id"),
        content=data.get("content"),
        location=data.get("location"),
    )
    db.session.add(post)
    try:
        db.session.commit()
    except:
        db.session.rollback()
        return jsonify({"message": "글 저장 실패"}), 400

    return jsonify({"message": "글 생성 완료"}), 200
