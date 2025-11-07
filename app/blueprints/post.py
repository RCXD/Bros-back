from flask import Blueprint, request, jsonify, current_app, send_from_directory
from ..models import Post, Image
from ..extensions import db
from flask_jwt_extended import jwt_required, get_jwt_identity, get_current_user
from sqlalchemy.orm import selectinload
from ..utils.image_storage import save_to_disk
from ..utils.image_utils import delete_image
from ..utils.image_compressor import compress_image
from ..utils.post_query import apply_order, paginate_posts, serialize_post

bp = Blueprint("post", __name__)


# ---------------- 1. 게시글 작성 ----------------
@bp.route("/write", methods=["POST"])
@jwt_required()
def write_post():
    user_id = get_jwt_identity()
    content = request.form.get("content")
    category_id = request.form.get("category_id")
    location = request.form.get("location")

    if not content:
        return jsonify({"error": "게시글 내용은 필수입니다."}), 400

    post = Post(
        user_id=user_id, category_id=category_id, content=content, location=location
    )
    db.session.add(post)
    db.session.flush()  # post_id 확보

    files = request.files.getlist("images")
    uploaded_images = []

    for file in files:
        if not file.filename:
            continue
        ext = file.filename.rsplit(".", 1)[-1].lower()
        if ext not in {"png", "jpg", "jpeg", "gif"}:
            db.session.rollback()
            return jsonify({"error": f"지원하지 않는 파일 형식: {file.filename}"}), 400
        try:
            output, ext = compress_image(file, image_type="post")
            rel_path = save_to_disk(output, ext, category="post")

            image = Image(
                post_id=post.post_id,
                user_id=user_id,
                directory=rel_path,
                original_image_name=file.filename,
                ext=ext,
            )
            db.session.add(image)
            db.session.flush()

            uploaded_images.append(
                {
                    "uuid": str(image.uuid),
                    "path": image.directory,
                    "original_name": image.original_image_name,
                }
            )
        except Exception as e:
            db.session.rollback()
            return jsonify({"error": f"이미지 저장 실패: {e}"}), 400

    try:
        db.session.commit()
        return (
            jsonify(
                {
                    "message": "게시글 작성 완료",
                    "post_id": post.post_id,
                    "uploaded_images": uploaded_images,
                }
            ),
            200,
        )
    except Exception as e:
        db.session.rollback()
        return jsonify({"error": f"게시글 저장 실패: {e}"}), 400


# ---------------- 2. 게시글 수정 ----------------
@bp.route("/edit/<int:post_id>", methods=["PUT"])
@jwt_required()
def edit_post(post_id):
    post = Post.query.get_or_404(post_id)
    current_user = get_current_user()
    if post.user_id != current_user.user_id:
        return jsonify({"error": "권한 없음"}), 403

    content = request.form.get("content")
    category_id = request.form.get("category_id")
    location = request.form.get("location")
    delete_uuids_raw = request.form.getlist("delete_images")
    delete_uuids = [u.strip().lower() for u in delete_uuids_raw if u.strip()]

    if content:
        post.content = content
    if category_id:
        post.category_id = category_id
    if location:
        post.location = location

    deleted, not_found = [], []

    if delete_uuids:
        post_images = Image.query.filter_by(post_id=post_id).all()
        uuid_map = {str(img.uuid).lower(): img for img in post_images}

        for u in delete_uuids:
            img = uuid_map.get(u)
            if img:
                try:
                    delete_image(img)
                except Exception as e:
                    print(f"[WARN] 파일 삭제 실패: {e}")
                db.session.delete(img)
                deleted.append(u)
            else:
                not_found.append(u)

        db.session.flush()

    new_files = request.files.getlist("new_images")
    uploaded_images = []

    for file in new_files:
        if not file.filename:
            continue
        ext = file.filename.rsplit(".", 1)[-1].lower()
        if ext not in {"png", "jpg", "jpeg", "gif"}:
            db.session.rollback()
            return jsonify({"error": f"지원하지 않는 파일 형식: {file.filename}"}), 400
        try:
            output, ext = compress_image(file, image_type="post")
            rel_path = save_to_disk(output, ext, category="post")

            image = Image(
                post_id=post.post_id,
                user_id=current_user.user_id,
                directory=rel_path,
                original_image_name=file.filename,
                ext=ext,
            )
            db.session.add(image)
            uploaded_images.append(
                {
                    "uuid": str(image.uuid),
                    "path": image.directory,
                    "original_name": image.original_image_name,
                }
            )
        except Exception as e:
            db.session.rollback()
            return jsonify({"error": f"이미지 저장 실패: {e}"}), 400

    try:
        db.session.commit()
        return (
            jsonify(
                {
                    "message": "게시글 수정 완료",
                    "post_id": post_id,
                    "uploaded_images": uploaded_images,
                    "deleted_images": deleted,
                    "not_found_images": not_found,
                }
            ),
            200,
        )
    except Exception as e:
        db.session.rollback()
        return jsonify({"error": f"게시글 수정 실패: {e}"}), 400


# ---------------- 3. 게시글 삭제 ----------------
@bp.route("/<int:post_id>", methods=["DELETE"])
@jwt_required()
def delete_post(post_id):
    post = Post.query.get_or_404(post_id)
    current_user = get_current_user()
    if post.user_id != current_user.user_id:
        return jsonify({"error": "권한 없음"}), 403

    try:
        for img in post.images:
            try:
                delete_image(img)
            except Exception as e:
                print(f"[WARN] 이미지 파일 삭제 실패: {e}")
            db.session.delete(img)
        db.session.delete(post)
        db.session.commit()
        return jsonify({"message": "게시글 및 이미지 삭제 완료"}), 200
    except Exception as e:
        db.session.rollback()
        return jsonify({"error": f"삭제 실패: {e}"}), 400


# ---------------- 4. 전체 게시글 조회 ----------------
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


# ---------------- 5. 특정 게시글 조회 ----------------
@bp.route("/<int:post_id>", methods=["GET"])
def get_post(post_id):
    post = Post.query.filter(Post.post_id == post_id).first_or_404()
    try:
        Post.add_view_counts(post)
        db.session.commit()
    except:
        db.session.rollback()
    return jsonify(serialize_post(post))


# ---------------- 6. 내 게시글 조회 ----------------
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

# img태그에서 이미지 조회하기를 위한 엔드포인트
@bp.route("/image/<string:uuid>", methods=["GET"])
def get_images(uuid):
    # uuid = request.get("uuid")
    image = Image.query.filter_by(uuid=uuid).first_or_404(description="이미지 없음")
    return send_from_directory(current_app.static_folder, image.directory)
    # return app.send_static_file(image.directory)

    # return jsonify(
    #     {
    #         "image_id": image.image_id,
    #         "post_id": image.post_id,
    #         "user_id": image.user_id,
    #         "original_image_name": image.original_image_name,
    #         "ext": image.ext,
    #         "created_at": image.created_at.isoformat(),
    #     }
    # )