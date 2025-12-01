"""
게시글 모듈 - 게시글 CRUD 및 상호작용
"""

from flask import Blueprint, jsonify, request, send_from_directory, session, current_app
from flask_jwt_extended import jwt_required, get_jwt_identity, get_current_user
from sqlalchemy.exc import IntegrityError

from apps.mention.models import Mention, MentionItemType
from apps.config.server import db
from apps.notification.models import Notification
from apps.notification.utils import create_mention_notification
from apps.post.models import CategoryType, Post, PostLike
from apps.post.validation_rule import (
    CategoryValidationError,
    parse_optional_positive_int,
    validate_category_payload,
)
from apps.post.thumbnail_util import (
    generate_post_thumbnail,
    remove_post_thumbnail,
    ThumbnailGenerationError,
)
from apps.image.models import Image
from apps.place.models import Place
from apps.auth.models import User
from apps.common.image_handlers import compress_image, save_to_disk, IMAGE_EXTENSIONS
from apps.user.models import Follow
from apps.user.reward_utils import (
    reward_post_like_received,
    reward_post_like_given,
    reward_view_threshold,
)

bp = Blueprint("post", __name__)
VIEWED_POSTS_SESSION_KEY = "viewed_posts"  # 세션에 저장할 조회된 게시물 ID 목록 키
MAX_VIEWED_RECORDS = 200  # 세션당 최대 조회 기록 수


def _detect_hazard_payload(form):
    """Pick the first non-empty hazard-related form field if provided."""

    for key in ("hazard_id", "hazard", "hazard_type"):
        raw_value = form.get(key)
        if raw_value is None:
            continue
        text = (
            raw_value.strip() if isinstance(raw_value, str) else str(raw_value).strip()
        )
        if text and text.lower() != "null":
            return text
    return None


def _serialize_place_summary(place):
    if not place:
        return None
    return {
        "place_id": place.place_id,
        "name": place.name,
        "route_id": getattr(place, "route_id", None),
        "category_id": place.category_id,
        "type_id": place.type_id,
    }


def _route_points_from_place(place):
    if not place:
        return []
    route = getattr(place, "route", None)
    points = getattr(route, "points", None)
    return points or []


def _route_points_for_post(post):
    if not post:
        return []
    return _route_points_from_place(getattr(post, "place", None))


def _serialize_image(image):
    if not image:
        return None
    return {
        "image_id": image.image_id,
        "uuid": getattr(image, "uuid", None),
        "directory": image.directory,
        "original_image_name": image.original_image_name,
        "ext": image.ext,
    }


def _active_post_images(post_id):
    return Image.query.filter(
        Image.post_id == post_id,
        Image.image_type.is_(None),
    ).all()


def _register_post_view(post_id):  # 세션에 게시물 조회 기록 등록
    viewed = session.get(VIEWED_POSTS_SESSION_KEY, [])
    if post_id in viewed:
        return False

    viewed.append(post_id)
    session[VIEWED_POSTS_SESSION_KEY] = viewed[-MAX_VIEWED_RECORDS:]
    return True


@bp.get("/api_info")
def api_info():
    """
    게시물 API 정보 제공 (개발용)
    """
    info = {
        "module": "post",
        "base_path": "/post",
        "description": "게시물 생성, 조회, 수정, 삭제 및 좋아요 관리",
        "endpoints": [
            {
                "path": "/post",
                "method": "POST",
                "auth_required": True,
                "description": "게시물 생성",
                "form_data": {
                    "content": "게시물 내용 (필수)",
                    "category": "카테고리 (필수, CategoryType 값)",
                    "images": "이미지 파일들 (선택, 다중 가능)",
                },
            },
            {
                "path": "/post/<post_id>",
                "method": "GET",
                "auth_required": False,
                "description": "특정 게시물 조회",
            },
            {
                "path": "/post/<post_id>",
                "method": "PUT",
                "auth_required": True,
                "description": "게시물 수정",
                "form_data": "content (선택)",
            },
            {
                "path": "/post/<post_id>",
                "method": "DELETE",
                "auth_required": True,
                "description": "게시물 삭제",
            },
            {
                "path": "/post",
                "method": "GET",
                "auth_required": False,
                "description": "게시물 목록 조회",
                "query_params": {
                    "category": "카테고리 필터 (선택)",
                    "page": "페이지 번호 (기본: 1)",
                    "per_page": "페이지당 개수 (기본: 20)",
                    "order_by": "정렬 (latest, popular)",
                },
            },
            {
                "path": "/post/<post_id>/like",
                "method": "POST",
                "auth_required": True,
                "description": "게시물 좋아요 추가",
            },
            {
                "path": "/post/<post_id>/like",
                "method": "DELETE",
                "auth_required": True,
                "description": "게시물 좋아요 취소",
            },
            {
                "path": "/post/category",
                "method": "GET",
                "auth_required": False,
                "description": "전체 카테고리 목록 조회",
            },
            {
                "path": "/post/api_info",
                "method": "GET",
                "auth_required": False,
                "description": "API 정보 조회 (개발용)",
            },
        ],
    }
    return jsonify(info), 200


from flask import g


@bp.get("")
def get_posts():
    owner_id = request.args.get("owner_id", None, type=int)
    page = request.args.get("page", 1, type=int)
    per_page = request.args.get("per_page", 20, type=int)
    category = request.args.get("category")
    order_by = request.args.get("order_by", "latest")

    query = Post.query

    if category:
        normalized_category = category.strip().upper()
        if not CategoryType.has(normalized_category):
            return jsonify({"message": "유효하지 않은 카테고리입니다"}), 400
        query = query.filter_by(category=normalized_category)
    if owner_id:
        query = query.filter_by(user_id=owner_id)
    if order_by == "popular":
        query = query.order_by(Post.view_counts.desc())
    else:
        query = query.order_by(Post.created_at.desc())

    pagination = query.paginate(page=page, per_page=per_page, error_out=False)

    posts = []
    current_user_id = getattr(g, "user_id", None)  # 현재 로그인 유저 ID

    for post in pagination.items:
        user = User.query.get(post.user_id)
        like_count = PostLike.query.filter_by(post_id=post.post_id).count()

        # ✅ 현재 유저가 좋아요 눌렀는지 확인
        is_liked = False
        if current_user_id:
            is_liked = (
                PostLike.query.filter_by(
                    post_id=post.post_id, user_id=current_user_id
                ).first()
                is not None
            )

        images = _active_post_images(post.post_id)
        posts.append(
            {
                "post_id": post.post_id,
                "author": {
                    "user_id": user.user_id if user else None,
                    "nickname": user.nickname if user else None,
                    "profile_img": user.profile_img if user else None,
                },
                "content": post.content,
                "category": post.category,
                "view_counts": post.view_counts,
                "like_count": like_count,
                "isLiked": is_liked,
                "images": [_serialize_image(img) for img in images],
                "thumbnail": _serialize_image(post.thumbnail),
                "place": _serialize_place_summary(post.place),
                "location_name": post.location_name,
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
        - category: 필수 (CategoryType 값)
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
        # category 또는 category_id 모두 지원 (하위 호환성)
        raw_category = request.form.get("category") or request.form.get("category_id")
        category_input = (raw_category or "").strip()

        if not content:
            return jsonify({"message": "내용은 필수입니다"}), 400
        if len(content) > 2000:
            return (
                jsonify({"message": "게시글 내용은 2000자 이하로 입력해야 합니다."}),
                400,
            )
        if not category_input:
            return jsonify({"message": "카테고리는 필수입니다"}), 400

        # 숫자 ID인 경우 이름으로 변환, 아니면 그대로 사용
        if category_input.isdigit():
            category_name = CategoryType.from_id(category_input)
            if not category_name:
                return jsonify({"message": "유효하지 않은 카테고리 ID입니다"}), 400
        else:
            category_name = category_input.upper()
            if not CategoryType.has(category_name):
                return jsonify({"message": "유효하지 않은 카테고리입니다"}), 400

        location_name_value = request.form.get("location_name")
        hazard_payload = _detect_hazard_payload(request.form)

        try:
            place_id = parse_optional_positive_int(
                request.form.get("place_id"), "place_id"
            )
            validation = validate_category_payload(
                category_name,
                place_id=place_id,
                hazard_payload=hazard_payload,
            )
        except CategoryValidationError as validation_error:
            return jsonify({"message": str(validation_error)}), 400

        linked_place = None
        if validation.place_id is not None:
            linked_place = db.session.get(Place, validation.place_id)
            if not linked_place:
                return jsonify({"message": "지정한 place_id를 찾을 수 없습니다."}), 404
            if category_name == CategoryType.ROUTE and not _route_points_from_place(
                linked_place
            ):
                return (
                    jsonify(
                        {
                            "message": "ROUTE 카테고리는 경로가 연결된 장소만 사용할 수 있습니다."
                        }
                    ),
                    400,
                )

        # 게시글 생성
        post = Post(
            user_id=current_user.user_id,
            category=category_name,
            content=content,
            place_id=validation.place_id,
        )
        if location_name_value is not None:
            post.location_name = location_name_value or None

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

        # 팔로워들에게 피드 생성 및 알림 발송
        # 나를 팔로우하는 사용자 조회 (to_user_id가 나인 Follow의 from_user_id)
        follower_ids = [
            f.from_user_id
            for f in Follow.query.filter_by(to_user_id=current_user.user_id).all()
        ]
        followers = (
            User.query.filter(User.user_id.in_(follower_ids)).all()
            if follower_ids
            else []
        )

        for follower in followers:
            # 피드 생성 (utils 함수 사용)
            from apps.feed.utils import create_new_post_feed

            feed_item = create_new_post_feed(
                user_id=follower.user_id,
                post_id=post.post_id,
                post_user_id=current_user.user_id,
            )

            # 알림 생성 (utils 함수 사용)
            from apps.notification.utils import create_new_post_notification

            create_new_post_notification(
                follower.user_id, current_user.user_id, post, feed_item
            )

        # Mention 생성 및 알림 발송
        mentioned_user_ids = []
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
                item_type=MentionItemType.POST,
                item_id=post.post_id,
            )
            db.session.add(mention)
            db.session.flush()  # mention 객체에 ID 할당

            # 알림 생성 (utils 함수 사용)
            create_mention_notification(
                current_user.user_id, mentioned_user_id, mention
            )

        thumbnail_info = None
        route_points = (
            _route_points_from_place(linked_place)
            if linked_place
            else _route_points_for_post(post)
        )
        current_app.logger.info(
            "썸네일 생성 시도: post_id=%s, place_id=%s, route_points=%s",
            post.post_id,
            post.place_id,
            route_points,
        )
        if route_points:
            try:
                thumbnail_image = generate_post_thumbnail(
                    post,
                    points=route_points,
                    provider="openstreet",
                    location_name=post.location_name,
                )
                thumbnail_info = _serialize_image(thumbnail_image)
                current_app.logger.info(
                    "썸네일 생성 성공 (post_id=%s, image_id=%s)",
                    post.post_id,
                    thumbnail_image.image_id,
                )
            except ThumbnailGenerationError as thumb_err:
                current_app.logger.warning(
                    "썸네일 생성 실패 (post_id=%s): %s",
                    post.post_id,
                    thumb_err,
                )

        db.session.commit()

        response_payload = {"message": "게시글이 작성되었습니다"}
        if uploaded_images:
            response_payload["uploaded_images"] = uploaded_images
        if thumbnail_info is not None:
            response_payload["thumbnail"] = thumbnail_info

        return jsonify(response_payload), 201

    except Exception as e:
        db.session.rollback()
        return jsonify({"message": f"게시글 작성 실패: {str(e)}"}), 400


@bp.get("/<int:post_id>")
def get_post(post_id):
    """ID로 단일 게시글 조회"""
    post = Post.query.get_or_404(post_id)

    # 세션당 중복 카운팅 방지
    if _register_post_view(post_id):
        old_views = post.view_counts
        post.add_view_counts()
        db.session.commit()

        # 조회수 임계값 달성 시 리워드 지급
        category_name = post.category or "default"
        reward_view_threshold(
            post_id=post.post_id,
            post_author_id=post.user_id,
            current_views=post.view_counts,
            category=category_name,
        )

    # 좋아요 수 조회
    like_count = PostLike.query.filter_by(post_id=post_id).count()

    # 작성자 정보 조회
    author = User.query.get(post.user_id)

    # ✅ 현재 유저가 좋아요 눌렀는지 확인
    is_liked = False
    current_user_id = getattr(g, "user_id", None)  # 현재 로그인 유저 ID

    if current_user_id:
        is_liked = (
            PostLike.query.filter_by(post_id=post_id, user_id=current_user_id).first()
            is not None
        )

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
                "category": post.category,
                "view_counts": post.view_counts,
                "like_count": like_count,
                "isLiked": is_liked,
                "images": [
                    _serialize_image(img) for img in _active_post_images(post.post_id)
                ],
                "thumbnail": _serialize_image(post.thumbnail),
                "place": _serialize_place_summary(post.place),
                "location_name": post.location_name,
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

        location_name_value = request.form.get("location_name")
        remove_thumbnail_flag = (
            request.form.get("remove_thumbnail") or ""
        ).lower() in (
            "1",
            "true",
            "yes",
        )
        should_refresh_thumbnail = False
        thumbnail_info = None
        thumbnail_removed = False

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
        if location_name_value is not None:
            post.location_name = location_name_value or None
            should_refresh_thumbnail = True

        if remove_thumbnail_flag and remove_post_thumbnail(post):
            thumbnail_removed = True
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
                    if image.image_type == "thumbnail":
                        continue
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

        route_points = _route_points_for_post(post)
        if should_refresh_thumbnail and route_points:
            try:
                new_thumb = generate_post_thumbnail(
                    post,
                    points=route_points,
                    provider="openstreet",
                    location_name=post.location_name,
                )
                thumbnail_info = _serialize_image(new_thumb)
                thumbnail_removed = False
            except ThumbnailGenerationError as thumb_err:
                current_app.logger.warning(
                    "썸네일 재생성 실패 (post_id=%s): %s",
                    post.post_id,
                    thumb_err,
                )

        db.session.commit()

        response = {"message": "게시글이 수정되었습니다"}
        if deleted_images:
            response["deleted_images"] = deleted_images
        if uploaded_images:
            response["uploaded_images"] = uploaded_images
        if thumbnail_removed:
            response["thumbnail"] = None
        elif thumbnail_info is not None:
            response["thumbnail"] = thumbnail_info

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


@bp.patch("/<int:post_id>/like")
@jwt_required()
def like_post(post_id):
    """게시글 좋아요 (토글)"""
    current_user_id = int(get_jwt_identity())

    # 게시글 존재 확인
    post = Post.query.get_or_404(post_id)

    # 이미 좋아요 했는지 확인
    existing = PostLike.query.filter_by(
        post_id=post_id, user_id=current_user_id
    ).first()

    if existing:
        # 좋아요 취소
        db.session.delete(existing)
        db.session.commit()
        like_count = PostLike.query.filter_by(post_id=post_id).count()
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
        like_count = PostLike.query.filter_by(post_id=post_id).count()

        # 리워드 지급 (자기 게시글 좋아요 제외)
        if post.user_id != current_user_id:
            category_name = post.category or "default"
            # 게시글 작성자에게 리워드
            reward_post_like_received(post.user_id, category=category_name)
            # 좋아요 누른 사람에게도 리워드
            reward_post_like_given(current_user_id)

        return (
            jsonify({"message": "좋아요", "liked": True, "like_count": like_count}),
            201,
        )


@bp.get("/me/liked-posts")
@jwt_required()
def get_my_likes_posts():
    """내가 좋아요 누른 포스트 번호 조회"""
    current_user_id = int(get_jwt_identity())
    likes = PostLike.query.filter_by(user_id=current_user_id).all()

    liked_post_ids = [like.post_id for like in likes]

    return jsonify({"liked_post_ids": liked_post_ids}), 200


@bp.get("/<int:post_id>/who-likes")
def get_post_likes(post_id):
    """게시글에 좋아요한 사용자 목록 조회"""
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

    return jsonify({"people_who_likes": result, "count": len(result)}), 200


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

        # ✅ 현재 유저가 좋아요 눌렀는지 확인
        is_liked = (
            PostLike.query.filter_by(
                post_id=post.post_id, user_id=current_user_id
            ).first()
            is not None
        )

        images = _active_post_images(post.post_id)
        posts.append(
            {
                "post_id": post.post_id,
                "content": post.content,
                "category": post.category,
                "view_counts": post.view_counts,
                "like_count": like_count,
                "isLiked": is_liked,
                "images": [_serialize_image(img) for img in images],
                "thumbnail": _serialize_image(post.thumbnail),
                "place": _serialize_place_summary(post.place),
                "location_name": post.location_name,
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


# =====================================================
# 게시글 이미지 조회
# =====================================================
# 이미지 조회는 /image/post/<uuid> 엔드포인트로 통합되었습니다.
# apps.image.views.get_post_image 참조
