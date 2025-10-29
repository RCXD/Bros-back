from flask import Blueprint, request, jsonify, current_app
from ..models import Post, Image
from ..extensions import db, jwt
from flask_jwt_extended import get_current_user, jwt_required, get_jwt_identity
from ..utils.image_storage import save_image, delete_image
import os


bp = Blueprint("post", __name__)


# ✅ 게시글 작성
@bp.route("/write", methods=["POST"])
@jwt_required()
def write():
    """
    ✅ 게시글 작성
    - 게시글 생성 후 post_id 반환
    - 이미지 업로드는 별도 엔드포인트에서 post_id 기반으로 수행
    """
    data = request.get_json() or {}
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


# ✅ 게시글 수정
@bp.route("/edit/<int:post_id>", methods=["PUT"])
@jwt_required()
def edit_post(post_id):
    """
    ✅ 게시글 수정
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


# ✅ 공통 정렬 함수
def apply_order(query, order_by):
    """정렬 기준을 적용하는 헬퍼 함수"""
    if order_by == "latest":
        return query.order_by(Post.created_at.desc())
    elif order_by == "oldest":
        return query.order_by(Post.created_at.asc())
    elif order_by == "popular" and hasattr(Post, "like_count"):
        return query.order_by(Post.like_count.desc(), Post.created_at.desc())
    else:
        return query.order_by(Post.created_at.desc())


# ✅ 전체 게시글 조회 (조건부 필터 + pagination + 정렬)
@bp.route("/posts", methods=["GET"])
def get_posts():
    filters = {}
    for key, value in request.args.items():
        if key not in ["page", "per_page", "order_by"] and value:
            filters[key] = value

    page = int(request.args.get("page", 1))
    per_page = int(request.args.get("per_page", 10))
    order_by = request.args.get("order_by", "latest")

    query = Post.query

    for key, value in filters.items():
        column = getattr(Post, key, None)
        if column is not None:
            query = query.filter(column.ilike(f"%{value}%"))

    query = apply_order(query, order_by)
    pagination = query.paginate(page=page, per_page=per_page, error_out=False)

    result = [
        {
            "post_id": p.post_id,
            "user_id": p.user_id,
            "category_id": p.category_id,
            "content": p.content,
            "location": p.location,
            "created_at": p.created_at.isoformat(),
            "updated_at": p.updated_at.isoformat() if p.updated_at else None,
        }
        for p in pagination.items
    ]

    return (
        jsonify(
            {
                "total": pagination.total,
                "page": pagination.page,
                "per_page": pagination.per_page,
                "pages": pagination.pages,
                "has_next": pagination.has_next,
                "has_prev": pagination.has_prev,
                "items": result,
            }
        ),
        200,
    )


# ✅ 특정 게시글 조회 (단일)
@bp.route("/posts/<int:post_id>", methods=["GET"])
def get_post(post_id):
    post = Post.query.get_or_404(post_id)
    return (
        jsonify(
            {
                "post_id": post.post_id,
                "user_id": post.user_id,
                "category_id": post.category_id,
                "content": post.content,
                "location": post.location,
                "created_at": post.created_at.isoformat(),
                "updated_at": post.updated_at.isoformat() if post.updated_at else None,
            }
        ),
        200,
    )


# ✅ 특정 유저의 게시글 조회 (pagination + 정렬)
@bp.route("/posts/user/<int:user_id>", methods=["GET"])
def get_user_posts(user_id):
    page = int(request.args.get("page", 1))
    per_page = int(request.args.get("per_page", 10))
    order_by = request.args.get("order_by", "latest")

    query = Post.query.filter_by(user_id=user_id)
    query = apply_order(query, order_by)
    pagination = query.paginate(page=page, per_page=per_page, error_out=False)

    result = [
        {
            "post_id": p.post_id,
            "category_id": p.category_id,
            "content": p.content,
            "location": p.location,
            "created_at": p.created_at.isoformat(),
            "updated_at": p.updated_at.isoformat() if p.updated_at else None,
        }
        for p in pagination.items
    ]
    return (
        jsonify(
            {
                "total": pagination.total,
                "page": pagination.page,
                "per_page": pagination.per_page,
                "pages": pagination.pages,
                "items": result,
            }
        ),
        200,
    )


# ✅ 카테고리별 게시글 조회 (pagination + 정렬)
@bp.route("/posts/categories/<int:category_id>", methods=["GET"])
def get_category_posts(category_id):
    page = int(request.args.get("page", 1))
    per_page = int(request.args.get("per_page", 10))
    order_by = request.args.get("order_by", "latest")

    query = Post.query.filter_by(category_id=category_id)
    query = apply_order(query, order_by)
    pagination = query.paginate(page=page, per_page=per_page, error_out=False)

    result = [
        {
            "post_id": p.post_id,
            "user_id": p.user_id,
            "content": p.content,
            "location": p.location,
            "created_at": p.created_at.isoformat(),
            "updated_at": p.updated_at.isoformat() if p.updated_at else None,
        }
        for p in pagination.items
    ]
    return (
        jsonify(
            {
                "total": pagination.total,
                "page": pagination.page,
                "per_page": pagination.per_page,
                "pages": pagination.pages,
                "items": result,
            }
        ),
        200,
    )


# ✅ 내 게시글 조회 (pagination + 정렬)
@bp.route("/posts/me", methods=["GET"])
@jwt_required()
def get_my_posts():
    current_user_id = get_jwt_identity()
    page = int(request.args.get("page", 1))
    per_page = int(request.args.get("per_page", 10))
    order_by = request.args.get("order_by", "latest")

    query = Post.query.filter_by(user_id=current_user_id)
    query = apply_order(query, order_by)
    pagination = query.paginate(page=page, per_page=per_page, error_out=False)

    result = [
        {
            "post_id": p.post_id,
            "category_id": p.category_id,
            "content": p.content,
            "location": p.location,
            "created_at": p.created_at.isoformat(),
            "updated_at": p.updated_at.isoformat() if p.updated_at else None,
        }
        for p in pagination.items
    ]
    return (
        jsonify(
            {
                "total": pagination.total,
                "page": pagination.page,
                "per_page": pagination.per_page,
                "pages": pagination.pages,
                "items": result,
            }
        ),
        200,
    )


@bp.route("/upload_post_image", methods=["POST"])
@jwt_required()
def upload_post_image():
    """
    ✅ 게시글 이미지 업로드
    - 게시글 작성 후 받은 post_id를 form-data로 전달받아 저장
    """
    user_id = get_jwt_identity()
    post_id = request.form.get("post_id")
    file = request.files.get("image")

    if not file or not post_id:
        return jsonify({"error": "post_id 또는 이미지 파일이 누락되었습니다."}), 400

    post = Post.query.get(post_id)
    if not post:
        return jsonify({"error": "해당 게시글이 존재하지 않습니다."}), 404

    if post.user_id != int(user_id):
        return (
            jsonify({"error": "해당 게시글에 이미지를 업로드할 권한이 없습니다."}),
            403,
        )

    # 이미지 저장
    relative_path = save_image(file, folder="static/post_images", image_type="post")

    image = Image(
        user_id=user_id,
        post_id=post_id,
        directory=relative_path,
        original_image_name=file.filename,
        ext=os.path.splitext(file.filename)[1].lower(),
    )

    db.session.add(image)
    db.session.commit()

    return (
        jsonify(
            {
                "message": "이미지 업로드 완료",
                "uuid": image.uuid,
                "path": relative_path,
                "post_id": post_id,
            }
        ),
        200,
    )


@bp.route("/delete_post_image/<string:uuid>", methods=["DELETE"])
@jwt_required()
def delete_post_image(uuid):
    user_id = get_jwt_identity()
    image = Image.query.filter_by(uuid=uuid, user_id=user_id).first()

    if not image:
        return jsonify({"error": "이미지를 찾을 수 없습니다."}), 404

    abs_path = os.path.join(current_app.root_path, image.directory)
    if os.path.exists(abs_path):
        os.remove(abs_path)

    db.session.delete(image)
    db.session.commit()

    return jsonify({"message": "이미지 삭제 완료", "uuid": uuid}), 200
