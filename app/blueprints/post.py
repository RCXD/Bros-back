from flask import Blueprint, request, jsonify, current_app, send_from_directory

from app.models.location import Location
from ..models import Post, Image
from ..extensions import db
from flask_jwt_extended import jwt_required, get_jwt_identity, get_current_user
from sqlalchemy.orm import selectinload
from ..utils.image_storage import save_to_disk
from ..utils.image_utils import delete_image, IMAGE_EXTENSIONS
from ..utils.image_compressor import compress_image
from ..utils.post_query import apply_order, paginate_posts, serialize_post

bp = Blueprint("post", __name__)


# ---------------- 1. 게시글 작성 ----------------
@bp.route("/write", methods=["POST"])
@jwt_required()
def write_post():
    import json  # [수정] JSON 파싱용

    user_id = get_jwt_identity()
    content = request.form.get("content")
    category_id = request.form.get("category_id")

    # [수정] 단일 위경도 필드도 받을 수 있음
    latitude = request.form.get("latitude", type=float)
    longitude = request.form.get("longitude", type=float)
    location_name = request.form.get("location_name")  # 선택
    recommend_point = request.form.get("recommend_point", type=int, default=0)
    risk_point = request.form.get("risk_point", type=int, default=0)

    # [수정] points 배열(JSON 문자열)
    points_raw = request.form.get("points")
    points = []
    if points_raw:
        try:
            points = json.loads(points_raw)  # [{"lat":..,"lng":..}, ...]
        except json.JSONDecodeError:
            return jsonify({"message": "points 형식이 올바르지 않습니다."}), 400

    if not content:
        return jsonify({"message": "게시글 내용은 필수입니다."}), 400
    if len(content) > 2000:
        return jsonify({"error": "게시글 내용은 2000자 이하로 입력해야 합니다."}), 400

    # 1) 게시글 생성 먼저
    post = Post(user_id=user_id, category_id=category_id, content=content)
    db.session.add(post)
    db.session.flush()  # post_id 확보

    # 2) Location 생성
    locations_to_add = []

    # 단일 위경도
    if latitude is not None and longitude is not None:
        locations_to_add.append(
            {"lat": latitude, "lng": longitude, "name": location_name}
        )

    # points 배열
    for idx, point in enumerate(points):
        locations_to_add.append(
            {
                "lat": point.get("lat"),
                "lng": point.get("lng"),
                "name": point.get("name"),
                "order_index": idx,
            }
        )

    for idx, loc in enumerate(locations_to_add):
        location = Location(
            post_id=post.post_id,
            latitude=loc["lat"],
            longitude=loc["lng"],
            location_name=loc.get("name") or location_name,
            recommend_point=recommend_point,
            risk_point=risk_point,
            order_index=loc.get("order_index", idx),  # [수정] 순서
        )
        db.session.add(location)

    # 3) 이미지 처리 (기존 코드)
    files = request.files.getlist("images")
    uploaded_images = []

    for file in files:
        if not hasattr(file, "filename") or not hasattr(file, "name"):
            return jsonify({"message": "파일명이 없습니다."}), 400
        if hasattr(file, "name") and not hasattr(file, "filename"):
            setattr(file, "filename", file.name)
        ext = file.filename.rsplit(".", 1)[-1].lower()
        if ext not in IMAGE_EXTENSIONS:
            db.session.rollback()
            return (
                jsonify({"message": f"지원하지 않는 파일 형식: {file.filename}"}),
                400,
            )
        try:
            image_compressed, ext, filename = compress_image(file, image_type="post")

            image = Image(
                post_id=post.post_id,
                user_id=user_id,
                directory="",
                original_image_name=file.filename,
                ext=ext,
            )

            db.session.add(image)
            db.session.flush()

            # 파일명 = uuid + 확장자
            filename = f"{image.uuid}.{ext}"

            # 저장
            rel_path = save_to_disk(image_compressed, ext, filename, category="post")

            # DB 경로 갱신
            image.directory = rel_path
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
            return jsonify({"message": f"이미지 저장 실패: {e}"}), 400

    # 4) 커밋
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
        return jsonify({"message": f"게시글 저장 실패: {e}"}), 400


# ---------------- 2. 게시글 수정 ----------------
@bp.route("/edit/<int:post_id>", methods=["PUT"])
@jwt_required()
def edit_post(post_id):
    post = Post.query.get_or_404(post_id)
    current_user = get_current_user()
    if post.user_id != current_user.user_id:
        return jsonify({"message": "권한 없음"}), 403

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
                # current_app.logger.info(
                #     f"[DEBUG] 삭제 시도 uuid={u}, path={img.directory}"
                # )
                try:
                    # result = delete_image(img, category="post")
                    # current_app.logger.info(f"[DELETE RESULT] {result}")
                    delete_image(img)
                except Exception as e:
                    # current_app.logger.warning(f"[WARN] 파일 삭제 실패: {e}")
                    print(f"[WARN] 파일 삭제 실패: {e}")
                db.session.delete(img)
                deleted.append(u)
            else:
                not_found.append(u)

        db.session.flush()

    new_files = request.files.getlist("new_images")
    uploaded_images = []

    for file in new_files:
        if not file or not hasattr(file, "filename"):
            continue
        ext = file.filename.rsplit(".", 1)[-1].lower()
        if ext not in {"png", "jpg", "jpeg", "gif"}:
            db.session.rollback()
            return (
                jsonify({"message": f"지원하지 않는 파일 형식: {file.filename}"}),
                400,
            )
        try:
            image_compressed, ext, filename = compress_image(file, image_type="post")
            image = Image(
                post_id=post.post_id,
                user_id=current_user.user_id,
                directory="",
                original_image_name=file.filename,
                ext=ext,
            )
            db.session.add(image)
            db.session.flush()  # image.uuid 생성됨

            # 2) 파일명은 DB의 uuid와 정확히 동일하게 (uuid + ext)
            filename = f"{image.uuid}.{ext}"

            # 3) 압축 및 저장
            rel_path = save_to_disk(image_compressed, ext, filename, category="post")

            # 4) DB 레코드의 directory 갱신
            image.directory = rel_path
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
            return jsonify({"message": f"이미지 저장 실패: {e}"}), 400

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
        return jsonify({"message": f"게시글 수정 실패: {e}"}), 400


# ---------------- 3. 게시글 삭제 ----------------
@bp.route("/<int:post_id>", methods=["DELETE"])
@jwt_required()
def delete_post(post_id):
    post = Post.query.get_or_404(post_id)
    current_user = get_current_user()
    if post.user_id != current_user.user_id:
        return jsonify({"message": "권한 없음"}), 403

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
        return jsonify({"message": f"삭제 실패: {e}"}), 400


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
    return send_from_directory(
        "/".join(image.directory.split("/")[:-1]), image.directory.split("/")[-1]
    )
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
