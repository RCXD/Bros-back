import json
import os
import random
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple

import pytest
from apps.config.server import db
from apps.auth.models import User, AccountType
from apps.post.models import CategoryType, Post
from apps.post.thumbnail_util import (
    generate_post_thumbnail,
    ThumbnailGenerationError,
)
from apps.place.models import Place, PlaceType
from apps.route.models import Route

try:
    from logger import get_logger
    from gen_post_helper import (
        ensure_categories,
        load_posts_from_json,
        create_username_to_userid_map,
        build_places_cache,
        resolve_place_id,
    )

    from gen_route import (
        ensure_place_for_route,
        ensure_route_place_type,
        extract_route_points,
    )
except ImportError:
    from apps.common.logger import get_logger
    from apps.test.gen.gen_post_helper import (
        ensure_categories,
        load_posts_from_json,
        create_username_to_userid_map,
        build_places_cache,
        resolve_place_id,
    )
    from apps.test.gen.gen_route import (
        ensure_place_for_route,
        ensure_route_place_type,
        extract_route_points,
    )


def _route_signature(points: List[Dict[str, float]]) -> Optional[str]:
    try:
        return json.dumps(points, sort_keys=True)
    except (TypeError, ValueError):  # pragma: no cover - defensive
        return None


def _build_route_payload(post_data: Dict) -> Dict:
    return {
        "points": post_data.get("points"),
        "start": post_data.get("start_location"),
        "end": post_data.get("dest_location"),
        "waypoints": post_data.get("waypoints"),
    }


def _route_name_from_post(post_data: Dict, fallback_index: int) -> str:
    candidates = [
        post_data.get("route_name"),
        post_data.get("name"),
        post_data.get("title"),
        post_data.get("place_name"),
        post_data.get("location_name"),
    ]

    for candidate in candidates:
        if isinstance(candidate, str):
            normalized = candidate.strip()
            if normalized:
                return normalized

    start_name = post_data.get("start_name") or post_data.get("start_location_name")
    dest_name = post_data.get("dest_name") or post_data.get("dest_location_name")
    if isinstance(start_name, str) and isinstance(dest_name, str):
        start_clean = start_name.strip()
        dest_clean = dest_name.strip()
        if start_clean and dest_clean:
            return f"{start_clean} -> {dest_clean}"

    return f"사용자 경로 {fallback_index:03d}"


def _ensure_route_for_post(
    *,
    user_id: int,
    route_name: str,
    route_points: List[Dict[str, float]],
    place_type: PlaceType,
    cache: Dict[Tuple[int, str], Route],
) -> Optional[int]:
    if not route_points:
        return None

    signature = _route_signature(route_points)
    key: Optional[Tuple[int, str]] = (user_id, signature) if signature else None

    route = cache.get(key) if key else None

    if not route:
        route = Route.query.filter_by(user_id=user_id, name=route_name).first()
        if (
            route
            and key
            and key not in cache
            and _route_signature(route.points or []) == signature
        ):
            cache[key] = route

    if not route:
        route = Route(user_id=user_id, name=route_name, points=route_points)
        db.session.add(route)
        db.session.flush()
        if key:
            cache[key] = route

    if route and not route.points:
        route.points = route_points

    ensure_place_for_route(route, place_type)
    return route.place.place_id if route and route.place else None


def _route_points_for_post(post: Post) -> List[Dict[str, float]]:
    place = getattr(post, "place", None)
    if not place:
        place = db.session.get(Place, post.place_id) if post.place_id else None
    route = getattr(place, "route", None) if place else None
    return route.points if route and route.points else []


@pytest.mark.no_cleanup
def test_generate_posts(fixture_app):
    """cat*.json 파일에서 게시글 데이터를 로드하여 데이터베이스에 생성"""

    log = get_logger()

    with fixture_app.app_context():
        log.info(f"\n[3/5] 게시글 생성")

        # 기존 사용자 가져오기
        users = User.query.filter_by(account_type=AccountType.USER).all()

        if not users:
            log.warning("  사용자를 찾을 수 없습니다. gen_user.py를 먼저 실행하세요!")
            pytest.skip("게시글을 생성할 사용자가 없습니다")

        log.debug(f"  {len(users)}명의 사용자 발견")

        # username -> user_id 매핑 생성
        username_to_userid = create_username_to_userid_map(users)

        # 카테고리 확인/생성
        category_names = [
            CategoryType.STORY,
            CategoryType.ROUTE,
            CategoryType.REVIEW,
            CategoryType.REPORT,
        ]
        categories = ensure_categories(category_names)
        log.debug(f"  {len(categories)}개 카테고리 준비 완료")

        # Route Place 타입/캐시 준비
        route_place_type = ensure_route_place_type()
        route_cache: Dict[Tuple[int, str], Route] = {}
        for existing_route in Route.query.all():
            if not existing_route.points:
                continue
            signature = _route_signature(existing_route.points)
            if signature:
                route_cache[(existing_route.user_id, signature)] = existing_route

        # Place 캐시 생성 (cat2, cat3에서 Place 연결을 위해)
        name_cache, coord_cache = build_places_cache()
        if name_cache:
            log.debug(f"  {len(name_cache)}개 Place 캐시 로드 완료")

        # JSON 파일에서 게시글 데이터 로드
        json_dir = os.path.join(os.path.dirname(__file__), "..", "json")
        posts = []
        base_time = datetime.now() - timedelta(days=60)
        total_posts = 0
        linked_posts = 0
        skipped_route_posts = 0

        for cat_idx in range(4):
            post_list = load_posts_from_json(json_dir, cat_idx)

            if not post_list:
                log.debug(f"  {category_names[cat_idx]}: JSON 파일 없음, 건너뜀")
                continue

            category_name = category_names[cat_idx]

            for post_data in post_list:
                # username을 user_id로 변환 (없으면 랜덤 선택)
                username = post_data.get("username", "")
                user_id = username_to_userid.get(username)

                if not user_id:
                    user_id = random.choice(users).user_id

                place_id = None
                location_name = post_data.get("place_name")

                if cat_idx == 1:  # ROUTE 카테고리
                    route_payload = _build_route_payload(post_data)
                    route_points = extract_route_points(route_payload)
                    if len(route_points) < 2:
                        skipped_route_posts += 1
                        continue

                    route_name = _route_name_from_post(
                        post_data, fallback_index=total_posts + len(posts) + 1
                    )
                    place_id = _ensure_route_for_post(
                        user_id=user_id,
                        route_name=route_name,
                        route_points=route_points,
                        place_type=route_place_type,
                        cache=route_cache,
                    )
                    if not place_id:
                        skipped_route_posts += 1
                        continue
                    if not location_name:
                        location_name = route_name
                    linked_posts += 1

                elif cat_idx in [2, 3] and (name_cache or coord_cache):
                    place_id = resolve_place_id(
                        post_data,
                        name_cache=name_cache,
                        coord_cache=coord_cache,
                        max_distance_m=300,
                    )
                    if place_id:
                        linked_posts += 1

                # Post 객체 생성
                post = Post(
                    user_id=user_id,
                    category=categories[cat_idx],
                    content=post_data.get("content", ""),
                    view_counts=random.randint(0, 1000),
                    created_at=base_time + timedelta(days=random.randint(0, 60)),
                    place_id=place_id,
                )
                if location_name:
                    post.location_name = location_name
                posts.append(post)

            total_posts += len(post_list)
            log.debug(f"  {category_name}: {len(post_list)}개 게시글 로드")

        # 데이터베이스에 저장
        if posts:
            db.session.add_all(posts)
            db.session.commit()

            route_thumbnail_targets = (
                Post.query.join(Place, Post.place_id == Place.place_id)
                .filter(Place.route_id.isnot(None), Post.thumbnail_id.is_(None))
                .all()
            )

            thumbnail_created = 0
            thumbnail_failed = 0
            for seeded_post in route_thumbnail_targets:
                points = _route_points_for_post(seeded_post)
                if not points:
                    continue
                try:
                    generate_post_thumbnail(
                        seeded_post,
                        points=points,
                        provider="openstreet",
                        location_name=seeded_post.location_name,
                    )
                    thumbnail_created += 1
                except ThumbnailGenerationError as thumb_err:
                    thumbnail_failed += 1
                    # Only log first 3 failures to avoid spam
                    if thumbnail_failed <= 3:
                        log.warning(
                            f"  [!] 썸네일 생성 실패 (post_id={seeded_post.post_id}): {thumb_err}"
                        )

            if thumbnail_created:
                db.session.commit()
                log.debug(f"  위치 썸네일 생성: {thumbnail_created}개")

            if thumbnail_failed > 3:
                log.warning(
                    f"  [!] 추가 {thumbnail_failed - 3}개 썸네일 생성 실패 (로그 생략)"
                )

            if thumbnail_failed > 0 and thumbnail_created == 0:
                osm_url = fixture_app.config.get("OPENSTREET_URL", "not configured")
                osm_endpoint = fixture_app.config.get(
                    "OPENSTREET_STATIC_ENDPOINT", "not configured"
                )
                log.warning(f"  [!] 모든 썸네일 생성 실패 ({thumbnail_failed}개)")
                log.info(f"  [i] 현재 OpenStreetMap 설정:")
                log.info(f"     OPENSTREET_URL={osm_url}")
                if osm_endpoint and osm_endpoint != "not configured":
                    log.info(f"     OPENSTREET_STATIC_ENDPOINT={osm_endpoint}")
                log.info(
                    f"  [i] 썸네일은 선택 기능입니다. 데이터 생성은 정상적으로 완료되었습니다."
                )

            # 게시글이 생성되었는지 확인
            final_count = Post.query.count()
            log.success(f"  {total_posts}개 게시글 생성 완료 (DB 총: {final_count}개)")
            if linked_posts > 0:
                log.success(f"  {linked_posts}개 게시글이 Place와 연결됨")
            if skipped_route_posts:
                log.warning(
                    f"  ROUTE 데이터 누락: {skipped_route_posts}개 게시글이 경로 정보 부족으로 건너뜀"
                )
        else:
            log.warning("  생성할 게시글이 없습니다")
