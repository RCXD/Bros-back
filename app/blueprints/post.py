from flask import Blueprint, request, jsonify
from ..models import Post, Image
from ..extensions import db, jwt
from flask_jwt_extended import get_current_user, jwt_required

bp = Blueprint("post", __name__)


@bp.route("/write", methods=['POST'])
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

@bp.route("/edit/<int:post_id>")
@jwt_required()
def edit_post(post_id):
    post = Post.query.get(post_id) or {}
    current_user=get_current_user() or {}
    if post.get('user_id') == current_user.get('user_id'):
      return jsonify({'error' : '권한 없음'}), 400
    
    data = request.get_json() or {}

    post.content = data['content']
    post.images = []
    for img_data in data['images']:
        image = Image.query.filter_by(uuid=img_data['uuid']).first()
        if image:
            post.images.append(image)

    db.session.commit()
    return jsonify({'message' : '게시글 수정 완료'}), 200