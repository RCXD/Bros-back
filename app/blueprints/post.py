from flask import Blueprint, request, jsonify
from ..models import Post, Image
from ..extensions import db
from flask_jwt_extended import jwt_required, get_jwt_identity, get_current_user
from sqlalchemy.orm import selectinload
from ..utils.image_storage import save_to_disk, delete_image
from ..utils.image_compressor import compress_image
from ..utils.post_query import apply_order, paginate_posts, serialize_post
import os

bp = Blueprint("post", __name__)


# 게시글 작성
@bp.route("/write", methods=["POST"])
@jwt_required()
def write():
    """
    게시글 작성
    - post_id 반환
    - 이미지 업로드는 별도 엔드포인트에서 수행
    """
    data = request.get_json()
    user_id = get_jwt_identity()
    post = Post(
        user_id=user_id,
        category_id=data.get("category_id"),
        content=data.get("content"),
        location=data.get("location"),
    )
    db.session.add(post)
    db.session.commit()
    return jsonify({"message": "게시글 생성 완료", "post_id": post.post_id}), 200


# 게시글 수정 (내용 + 이미지 삭제 통합)
@bp.route("/edit/<int:post_id>", methods=["PUT"])
@jwt_required()
def edit_post(post_id):
    """
    게시글 수정
    - 내용, 카테고리, 위치 수정
    - delete_images[] 포함 시 이미지 삭제
    """
    post = Post.query.get_or_404(post_id)
    current_user = get_current_user()
    if post.user_id != current_user.user_id:
        return jsonify({"error": "권한 없음"}), 403

    data = request.get_json() or {}
    post.content = data.get("content", post.content)
    post.category_id = data.get("category_id", post.category_id)
    post.location = data.get("location", post.location)

    delete_uuids = data.get("delete_images", [])
    if delete_uuids:
        images = Image.query.filter(
            Image.uuid.in_(delete_uuids), Image.post_id == post_id
        ).all()
        for img in images:
            delete_image(img)
            db.session.delete(img)

    try:
        db.session.commit()
        return jsonify({"message": "게시글 수정 완료", "post_id": post_id}), 200
    except Exception:
        db.session.rollback()
        return jsonify({"message": "게시글 수정 실패"}), 400


# 게시글 삭제 (연결된 이미지 포함)
@bp.route("/<int:post_id>", methods=["DELETE"])
@jwt_required()
def delete_post_full(post_id):
    current_user = get_current_user()
    post = Post.query.get_or_404(post_id)
    if post.user_id != current_user.user_id:
        return jsonify({"message": "권한 없음"}), 403

    try:
        for img in post.images:
            delete_image(img)
            db.session.delete(img)
        db.session.delete(post)
        db.session.commit()
        return jsonify({"message": "게시글 및 이미지 삭제 완료"}), 200
    except Exception:
        db.session.rollback()
        return jsonify({"message": "삭제 실패"}), 400


# 전체 게시글 조회
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
            query = query.filter(column.ilike(f"%{value}%"))

    query = apply_order(query, order_by)
    return paginate_posts(query, page, per_page)


# 특정 게시글 조회
@bp.route("/<int:post_id>", methods=["GET"])
def get_post(post_id):
    post = Post.query.filter(Post.post_id == post_id).first_or_404()
    try:
        Post.add_view_counts(post)
        db.session.commit()
    except:
        db.session.rollback()
    return jsonify(serialize_post(post))


# 내 게시글 조회
@bp.route("/me", methods=["GET"])
@jwt_required()
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


# 이미지 업로드
@bp.route("/upload_post_image", methods=["POST"])
@jwt_required()
def upload_post_image():
    """
    게시글 이미지 업로드 (여러 장 지원)
        - multipart/form-data로 여러 이미지 업로드 가능
    """
    user_id = get_jwt_identity()
    post_id = request.form.get("post_id")
    files = request.files.getlist("image")

    if not files or not post_id:
        return jsonify({"error": "필수 데이터 누락"}), 400

    uploaded_images = []

    for file in files:
        try:
            output, ext = compress_image(file, image_type="post")
            rel_path = save_to_disk(output, ext, category="post")

            image = Image(
                post_id=post_id,
                user_id=user_id,
                directory=rel_path,
                original_image_name=file.filename,
                ext=os.path.splitext(file.filename)[1].lstrip("."),
            )
            db.session.add(image)
            db.session.flush()  # commit 전 UUID 확보

            uploaded_images.append(
                {
                    "uuid": image.uuid,
                    "path": image.directory,
                    "original_name": image.original_image_name,
                }
            )

        except Exception as e:
            db.session.rollback()
            return jsonify({"error": f"이미지 저장 실패: {e}"}), 400

    db.session.commit()

    return (
        jsonify(
            {
                "message": f"{len(uploaded_images)}개 이미지 업로드 완료",
                "images": uploaded_images,
            }
        ),
        200,
    )


# 게시글의 이미지 전체 조회
@bp.route("/images/<int:post_id>", methods=["GET"])
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
