"""
게시글 모듈 - 게시글 CRUD 및 상호작용
"""

from flask import Blueprint, jsonify, request, send_from_directory
from flask_jwt_extended import jwt_required, get_jwt_identity, get_current_user
from sqlalchemy.exc import IntegrityError

from apps.mention.models import Mention
from apps.config.server import db
from apps.notification.models import Notification
from apps.post.models import Post, Category, PostLike, Image
from apps.auth.models import User
from apps.common.image_handlers import compress_image, save_to_disk, IMAGE_EXTENSIONS

bp = Blueprint("post", __name__)


@bp.get("")
def get_posts():
    """
    페이지네이션 및 필터링을 포함한 게시글 목록 조회
    Query params:
        - page: 페이지 번호
        - per_page: 페이지당 항목 수
        - category: 카테고리별 필터
        - order_by: 정렬 순서 (latest, popular 등)
    """
    page = request.args.get("page", 1, type=int)
    per_page = request.args.get("per_page", 20, type=int)
    category = request.args.get("category")
    order_by = request.args.get("order_by", "latest")

    query = Post.query

    # 카테고리별 필터링
    if category:
        cat = Category.query.filter_by(category_name=category).first()
        if cat:
            query = query.filter_by(category_id=cat.category_id)

    # 정렬
    if order_by == "popular":
        query = query.order_by(Post.view_counts.desc())
    else:  # latest
        query = query.order_by(Post.created_at.desc())

    # 페이지네이션
    pagination = query.paginate(page=page, per_page=per_page, error_out=False)

    posts = []
    for post in pagination.items:
        user = User.query.get(post.user_id)
        like_count = PostLike.query.filter_by(post_id=post.post_id).count()
        images = Image.query.filter_by(post_id=post.post_id).all()
        posts.append(
            {
                "post_id": post.post_id,
                "author": {
                    "user_id": user.user_id if user else None,
                    "nickname": user.nickname if user else None,
                    "profile_img": user.profile_img if user else None,
                },
                "content": post.content,
                "category": post.category.category_name if post.category else None,
                "view_counts": post.view_counts,
                "like_count": like_count,
                "images": [
                    {
                        "image_id": img.image_id,
                        "uuid": img.uuid,
                        "directory": img.directory,
                        "original_image_name": img.original_image_name,
                        "ext": img.ext,
                    }
                    for img in images
                ],
                "created_at": post.created_at.isoformat(),
                "updated_at": post.updated_at.isoformat(),
            }
        )

    return (
        jsonify(
            {
                "items": posts,
                "total": pagination.total,
                "pages": pagination.pages,
                "page": page,
                "per_page": per_page,
                "has_next": pagination.has_next,
                "has_prev": pagination.has_prev,
            }
        ),
        200,
    )


@bp.post("")
@jwt_required()
def create_post():
    """
    새 게시글 작성
    Form data:
        - content: 필수
        - category_id: 필수
        - images: 선택 (다중 파일)
        - mentions: 선택 (멘션된 사용자 ID 목록, 쉼표로 구분)
    """
    from apps.common.image_handlers import (
        compress_image,
        save_to_disk,
        IMAGE_EXTENSIONS,
    )

    try:
        current_user = get_current_user()
        content = request.form.get("content")
        category_id = request.form.get("category_id", type=int)

        if not content:
            return jsonify({"message": "내용은 필수입니다"}), 400
        if len(content) > 2000:
            return (
                jsonify({"message": "게시글 내용은 2000자 이하로 입력해야 합니다."}),
                400,
            )
        if not category_id:
            return jsonify({"message": "카테고리는 필수입니다"}), 400

        # 카테고리 존재 확인
        category = Category.query.get(category_id)
        if not category:
            return jsonify({"message": "유효하지 않은 카테고리입니다"}), 400

        # 게시글 생성
        post = Post(
            user_id=current_user.user_id, category_id=category_id, content=content
        )

        db.session.add(post)
        db.session.flush()  # post_id 확보

        # 이미지 업로드 처리
        files = request.files.getlist("images")
        uploaded_images = []

        for file in files:
            if not file or not hasattr(file, "filename"):
                continue

            # 파일 확장자 검증
            ext = file.filename.rsplit(".", 1)[-1].lower()
            if ext not in IMAGE_EXTENSIONS:
                raise ValueError(f"지원하지 않는 파일 형식: {file.filename}")

            # Image 레코드 생성 (UUID 자동 생성)
            image = Image(
                post_id=post.post_id,
                user_id=current_user.user_id,
                directory="",
                original_image_name=file.filename,
                ext=ext,
            )
            db.session.add(image)
            db.session.flush()  # UUID 생성

            # UUID로 파일명 생성하여 저장
            filename = f"{image.uuid}.{ext}"
            rel_path = save_to_disk(file, ext, filename, category="post")
            image.directory = rel_path
            db.session.flush()

            uploaded_images.append(
                {
                    "uuid": str(image.uuid),
                    "path": image.directory,
                    "original_name": image.original_image_name,
                }
            )

        # Mention 생성 및 알림 발송
        mentioned_ids = request.form.get("mentions")
        if mentioned_ids:
            try:
                mentioned_user_ids = [
                    int(uid.strip()) for uid in mentioned_ids.split(",") if uid.strip()
                ]
            except ValueError:
                return (
                    jsonify({"message": "유효하지 않은 멘션 사용자 ID 형식입니다"}),
                    400,
                )

        for mentioned_user_id in mentioned_user_ids:
            mention = Mention(
                mentioner_id=current_user.user_id,
                mentioned_user_id=mentioned_user_id,
                post_id=post.post_id,
            )
            notification = Notification(
                type="MENTION",
                from_user_id=current_user.user_id,
                to_user_id=mentioned_user_id,
                post_id=post.post_id,
            )

            db.session.add(mention)
            db.session.add(notification)

        db.session.commit()

        return jsonify({"message": "게시글이 작성되었습니다"}), 201

    except Exception as e:
        db.session.rollback()
        return jsonify({"message": f"게시글 작성 실패: {str(e)}"}), 400


@bp.get("/<int:post_id>")
def get_post(post_id):
    """ID로 단일 게시글 조회"""
    post = Post.query.get_or_404(post_id)

    # 조회수 증가
    post.add_view_counts()
    db.session.commit()

    # 좋아요 수 조회
    like_count = PostLike.query.filter_by(post_id=post_id).count()

    # 작성자 정보 조회
    author = User.query.get(post.user_id)

    return (
        jsonify(
            {
                "post_id": post.post_id,
                "author": (
                    {"nickname": author.nickname, "profile_img": author.profile_img}
                    if author
                    else None
                ),
                "content": post.content,
                "category": post.category.category_name if post.category else None,
                "view_counts": post.view_counts,
                "like_count": like_count,
                "created_at": post.created_at.isoformat(),
                "updated_at": post.updated_at.isoformat(),
            }
        ),
        200,
    )


@bp.put("/<int:post_id>")
@jwt_required()
def update_post(post_id):
    """
    게시글 수정
    Form data:
        - content: 선택 (게시글 내용)
        - images: 선택 (새 이미지 추가)
        - new_images: 선택 (새 이미지 추가, 'images'와 동일)
        - delete_image_ids: 선택 (삭제할 이미지 ID 목록, 쉼표로 구분)
    """
    from apps.common.image_handlers import delete_image

    try:
        current_user = get_current_user()
        post = Post.query.get_or_404(post_id)

        # 소유권 확인
        if post.user_id != current_user.user_id:
            return jsonify({"message": "권한이 없습니다"}), 403

        # 내용 수정
        content = request.form.get("content")
        if content:
            if len(content) > 2000:
                return (
                    jsonify(
                        {"message": "게시글 내용은 2000자 이하로 입력해야 합니다."}
                    ),
                    400,
                )
            post.content = content

        deleted_images = []
        # 이미지 삭제 처리
        delete_image_ids = request.form.get("delete_image_ids")
        if delete_image_ids:
            # 쉼표로 구분된 문자열을 리스트로 변환
            try:
                image_ids = [
                    int(img_id.strip())
                    for img_id in delete_image_ids.split(",")
                    if img_id.strip()
                ]
            except ValueError:
                return jsonify({"message": "유효하지 않은 이미지 ID 형식입니다"}), 400

            for img_id in image_ids:
                image = Image.query.filter_by(
                    image_id=img_id, post_id=post.post_id
                ).first()
                if image:
                    # 삭제 전 정보 저장
                    deleted_images.append(
                        {
                            "uuid": str(image.uuid),
                            "original_name": image.original_image_name,
                        }
                    )
                    # 파일 시스템에서 이미지 삭제
                    delete_image(image, category="post")
                    # DB에서 이미지 레코드 삭제
                    db.session.delete(image)
                else:
                    # 해당 게시글의 이미지가 아니거나 존재하지 않는 이미지
                    db.session.rollback()
                    return (
                        jsonify(
                            {
                                "message": f"이미지 ID {img_id}를 찾을 수 없거나 권한이 없습니다"
                            }
                        ),
                        404,
                    )

        # 새 이미지 업로드 처리
        files = request.files.getlist("images")
        if not files or len(files) == 0:
            # 'images' 키가 없으면 'new_images' 키 시도
            files = request.files.getlist("new_images")

        uploaded_images = []

        for file in files:
            if not file or not hasattr(file, "filename") or file.filename == "":
                continue

            # 파일 확장자 검증
            ext = file.filename.rsplit(".", 1)[-1].lower()
            if ext not in IMAGE_EXTENSIONS:
                raise ValueError(f"지원하지 않는 파일 형식: {file.filename}")

            # Image 레코드 생성 (UUID 자동 생성)
            image = Image(
                post_id=post.post_id,
                user_id=current_user.user_id,
                directory="",
                original_image_name=file.filename,
                ext=ext,
            )
            db.session.add(image)
            db.session.flush()  # UUID 생성

            # UUID로 파일명 생성하여 저장
            filename = f"{image.uuid}.{ext}"
            rel_path = save_to_disk(file, ext, filename, category="post")
            image.directory = rel_path
            db.session.flush()

            uploaded_images.append(
                {
                    "uuid": str(image.uuid),
                    "path": image.directory,
                    "original_name": image.original_image_name,
                }
            )

        db.session.commit()

        response = {"message": "게시글이 수정되었습니다"}
        if deleted_images:
            response["deleted_images"] = deleted_images
        if uploaded_images:
            response["uploaded_images"] = uploaded_images

        return jsonify(response), 200

    except Exception as e:
        db.session.rollback()
        return jsonify({"message": f"게시글 수정 실패: {str(e)}"}), 400


@bp.delete("/<int:post_id>")
@jwt_required()
def delete_post(post_id):
    """게시글 삭제"""
    try:
        current_user = get_current_user()
        post = Post.query.get_or_404(post_id)

        # 소유권 확인
        if post.user_id != current_user.user_id:
            return jsonify({"message": "권한이 없습니다"}), 403

        # 연관된 알림 먼저 삭제 (CASCADE가 DB에 적용되지 않은 경우 대비)
        from apps.notification.models import Notification

        Notification.query.filter_by(post_id=post_id).delete()

        # 댓글의 알림도 삭제 (post에 달린 모든 댓글)
        from apps.reply.models import Reply

        replies = Reply.query.filter_by(post_id=post_id).all()
        for reply in replies:
            Notification.query.filter_by(reply_id=reply.reply_id).delete()

        db.session.delete(post)
        db.session.commit()

        return jsonify({"message": "게시글이 삭제되었습니다"}), 200

    except Exception as e:
        db.session.rollback()
        return jsonify({"message": f"게시글 삭제 실패: {str(e)}"}), 400


@bp.post("/<int:post_id>/like")
@jwt_required()
def like_post(post_id):
    """게시글 좋아요 (토글)"""
    current_user_id = int(get_jwt_identity())

    # 게시글 존재 확인
    Post.query.get_or_404(post_id)

    # 이미 좋아요 했는지 확인
    existing = PostLike.query.filter_by(
        post_id=post_id, user_id=current_user_id
    ).first()

    like_count = PostLike.query.filter_by(post_id=post_id).count()

    if existing:
        # 좋아요 취소
        db.session.delete(existing)
        db.session.commit()
        return (
            jsonify(
                {"message": "좋아요 취소", "liked": False, "like_count": like_count}
            ),
            200,
        )
    else:
        # 좋아요
        like = PostLike(post_id=post_id, user_id=current_user_id)
        db.session.add(like)
        db.session.commit()
        return (
            jsonify({"message": "좋아요", "liked": True, "like_count": like_count}),
            201,
        )


@bp.delete("/<int:post_id>/like")
@jwt_required()
def unlike_post(post_id):
    """게시글 좋아요 취소"""
    current_user_id = int(get_jwt_identity())

    like = PostLike.query.filter_by(post_id=post_id, user_id=current_user_id).first()

    # if not like:
    #     return jsonify({"message": "좋아요하지 않은 게시글입니다"}), 404

    if like:
        db.session.delete(like)
        db.session.commit()

    return jsonify({"message": "좋아요 취소"}), 200


@bp.get("/<int:post_id>/likes")
def get_post_likes(post_id):
    """게시글에 좋아요한 사용자 목록 조회"""
    # 게시글 존재 확인
    Post.query.get_or_404(post_id)

    likes = PostLike.query.filter_by(post_id=post_id).all()

    result = []
    for like in likes:
        user = User.query.get(like.user_id)
        if user:
            result.append(
                {
                    "user_id": user.user_id,
                    "username": user.username,
                    "nickname": user.nickname,
                    "profile_img": user.profile_img,
                }
            )

    return jsonify({"likes": result, "count": len(result)}), 200


@bp.get("/me")
@jwt_required()
def get_my_posts():
    """현재 사용자의 게시글 조회"""
    current_user_id = int(get_jwt_identity())
    page = request.args.get("page", 1, type=int)
    per_page = request.args.get("per_page", 20, type=int)

    pagination = (
        Post.query.filter_by(user_id=current_user_id)
        .order_by(Post.created_at.desc())
        .paginate(page=page, per_page=per_page, error_out=False)
    )

    posts = []
    for post in pagination.items:
        like_count = PostLike.query.filter_by(post_id=post.post_id).count()
        images = Image.query.filter_by(post_id=post.post_id).all()
        posts.append(
            {
                "post_id": post.post_id,
                "content": post.content,
                "category": post.category.category_name if post.category else None,
                "view_counts": post.view_counts,
                "like_count": like_count,
                "images": [
                    {
                        "image_id": img.image_id,
                        "uuid": img.uuid,
                        "directory": img.directory,
                        "original_image_name": img.original_image_name,
                        "ext": img.ext,
                    }
                    for img in images
                ],
                "created_at": post.created_at.isoformat(),
                "updated_at": post.updated_at.isoformat(),
            }
        )

    return (
        jsonify(
            {
                "items": posts,
                "total": pagination.total,
                "pages": pagination.pages,
                "page": page,
            }
        ),
        200,
    )


@bp.get("/image/<string:uuid>")
def get_post_image(uuid):
    """
    이미지 파일 조회
    Path params:
        - uuid: 이미지 UUID
    Returns:
        - 이미지 파일

    Note: /image/ 와 /images/ 모두 지원
    """
    image = Image.query.filter_by(uuid=uuid).first_or_404(description="이미지 없음")
    return send_from_directory(
        "/".join(image.directory.split("/")[:-1]), image.directory.split("/")[-1]
    )
