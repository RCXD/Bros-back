from flask import Blueprint, request, jsonify, current_app
from ..models import Post, Image
from ..extensions import db, jwt
from flask_jwt_extended import get_current_user, jwt_required, get_jwt_identity
from ..utils.image_storage import save_to_disk, delete_image
import os
from ..utils.image_compressor import compress_image
from sqlalchemy.orm import selectinload
from ..utils.post_query import apply_order, paginate_posts, serialize_post


bp = Blueprint("post", __name__)


#  게시글 작성
@bp.route("/write", methods=["POST"])
@jwt_required()
def write():
    """
     게시글 작성
    - 게시글 생성 후 post_id 반환
    - 이미지 업로드는 별도 엔드포인트에서 post_id 기반으로 수행
    """
    data = request.files
    user_id = get_jwt_identity()

    post = Post(
        user_id=user_id,
        category_id=data.get("category_id"),
        content=data.get("content"),
        location=data.get("location"),
    )
    db.session.add(post)
    db.session.commit()  # commit해야 post_id 생성됨

    return (
        jsonify(
            {
                "message": "게시글 생성 완료",
                "post_id": post.post_id,  # 프론트가 이 값을 받아 이미지 업로드에 사용
            }
        ),
        200,
    )


# 게시글 수정
@bp.route("/edit/<int:post_id>", methods=["PUT"])
@jwt_required()
def edit_post(post_id):
    """
     게시글 수정
    - 내용 수정
    - 이미지 추가/삭제는 별도 엔드포인트에서 처리
    """
    post = Post.query.get_or_404(post_id)
    current_user = get_current_user()

    if post.user_id != current_user.user_id:
        return jsonify({"error": "권한 없음"}), 403

    data = request.get_json() or {}
    post.content = data.get("content", post.content)
    post.location = data.get("location", post.location)
    post.category_id = data.get("category_id", post.category_id)

    db.session.commit()
    return jsonify({"message": "게시글 수정 완료", "post_id": post_id}), 200


# 게시글 삭제
@bp.route("/", methods=["DELETE"])
def delete_post():
    current_user = get_current_user()
    post = Post.query.get_or_404(request.args.get("post_id", type=int))
    if post.user_id is not current_user.user_id:
        return jsonify({"message": "다른 유저의 글은 삭제할 수 없습니다"}), 403
    try:
        db.session.delete(post)
    except:
        db.session.commit()
    return jsonify({"message": "게시글이 삭제되었습니다"}), 200


#  전체 게시글 조회 (조건부 필터 + pagination + 정렬)
@bp.route("/posts", methods=["GET"])
def get_posts():
    filters = {
        key: value
        for key, value in request.args.items()
        if key not in ["page", "per_page", "order_by"] and value
    }
    page = request.args.get("page", 1, type=int)
    per_page = request.args.get("per_page", 10, type=int)
    order_by = request.args.get("order_by", "latest")
    query = Post.query.options(selectinload(Post.images))

    for key, value in filters.items():
        column = getattr(Post, key, None)
        if column is not None:
            query = query.filter(column.ilike(f"%{value}"))

    query = apply_order(query, order_by)

    return paginate_posts(query, page, per_page)


@bp.route("/mine")
@jwt_required
def get_my_posts():
    current_user = get_current_user()
    page = request.args.get("page", 1, type=int)
    per_page = request.args.get("per_page", 10, type=int)
    order_by = request.args.get("order_by", "latest")

    query = Post.query.filter_by(user_id=current_user.user_id).options(
        selectinload(Post.images)
    )
    query = apply_order(query, order_by)
    return paginate_posts(query, page, per_page)


@bp.route("/upload_post_image", methods=["POST"])
@jwt_required()
def upload_post_image():
    """
     게시글 이미지 업로드
    - 이미지 저장 후 DB에 메타데이터 반영
    """
    user_id = get_jwt_identity()
    post_id = request.form.get("post_id")
    file = request.files.get("image")

    if not file or not post_id:
        return jsonify({"error": "필수 데이터 누락"}), 400

    # 이미지 저장 및 메타데이터 획득
    try:
        output, ext = compress_image(file, image_type="post")
        _, rel_path = save_to_disk(output, ext, category="post")
    except Exception as e:
        return jsonify({"error": f"이미지 저장 실패: {e}"}), 400

    post = Post.query.get(post_id)
    if not post:
        return jsonify({"error": "게시글이 존재하지 않습니다."}), 404

    #  DB에 Image 객체 생성
    image = Image(
        post_id=post_id,
        user_id=user_id,
        directory=rel_path,
        original_image_name=file.filename,
        ext=os.path.splitext(file.filename)[1].lstrip("."),
    )

    db.session.add(image)
    db.session.commit()

    return (
        jsonify(
            {
                "message": "이미지 업로드 완료",
                "image": {
                    "uuid": image.uuid,
                    "path": image.directory,
                    "original_name": image.original_image_name,
                },
            }
        ),
        200,
    )


@bp.route("/delete_post_image/<string:uuid>", methods=["DELETE"])
@jwt_required()
def delete_post_image(uuid):
    user_id = get_jwt_identity()
    image = Image.query.filter_by(uuid=uuid, user_id=user_id).first()

    result = delete_image(image)

    if result:
        try:
            db.session.delete(image)
        except:
            db.session.rollback()
        db.session.commit()

    return jsonify({"message": "이미지 삭제 완료", "uuid": uuid}), 200


@bp.route("/<int:post_id>/images", methods=["GET"])
def get_post_images(post_id):
    images = Image.query.filter_by(post_id=post_id).all()
    return (
        jsonify(
            [
                {
                    "uuid": img.uuid,
                    "path": img.directory,
                    "original_name": img.original_image_name,
                }
                for img in images
            ]
        ),
        200,
    )
