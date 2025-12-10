"""
Post-Place 연결 검증 스크립트
"""

import pytest
from apps.config.server import db
from apps.post.models import Post, Category
from apps.place.models import Place


@pytest.mark.no_cleanup
def test_verify_post_place_linkage(fixture_app):
    """Post-Place 연결 상태 검증"""

    with fixture_app.app_context():
        print("\n" + "=" * 60)
        print("Post-Place 연결 검증")
        print("=" * 60)

        # 전체 Post 수
        total_posts = Post.query.count()
        print(f"\n총 게시글 수: {total_posts}")

        # Place 연결된 Post 수
        linked_posts = Post.query.filter(Post.place_id.isnot(None)).count()
        print(f"Place 연결된 게시글 수: {linked_posts}")

        # 카테고리별 통계
        print("\n카테고리별 Place 연결 현황:")
        categories = Category.query.all()

        for cat in categories:
            cat_total = Post.query.filter_by(category_id=cat.category_id).count()
            cat_linked = Post.query.filter(
                Post.category_id == cat.category_id, Post.place_id.isnot(None)
            ).count()

            if cat_total > 0:
                percent = (cat_linked / cat_total) * 100
                print(
                    f"  {cat.category_name}: {cat_linked}/{cat_total} ({percent:.1f}%)"
                )

        # Place별 연결된 Post 수
        print("\n가장 많이 참조된 Place Top 10:")
        linked_places = (
            db.session.query(
                Place.name, db.func.count(Post.post_id).label("post_count")
            )
            .join(Post, Post.place_id == Place.place_id)
            .group_by(Place.place_id)
            .order_by(db.func.count(Post.post_id).desc())
            .limit(10)
            .all()
        )

        for place_name, count in linked_places:
            print(f"  {place_name}: {count}개 게시글")

        # 연결된 Post 샘플 출력
        print("\n연결된 게시글 샘플 (최대 5개):")
        sample_posts = Post.query.filter(Post.place_id.isnot(None)).limit(5).all()

        for post in sample_posts:
            place = Place.query.get(post.place_id)
            content_preview = (
                post.content[:50] + "..." if len(post.content) > 50 else post.content
            )
            print(f"\n  [Post #{post.post_id}]")
            print(f"    내용: {content_preview}")
            print(f"    연결된 Place: {place.name if place else 'Unknown'}")
            if place:
                lat, lon = place.get_coordinates()
                print(f"    Place 좌표: ({lat}, {lon})")

        print("\n" + "=" * 60)
        print("✅ 검증 완료")
        print("=" * 60)


@pytest.mark.no_cleanup
def test_verify_place_cache(fixture_app):
    """Place 캐시 빌드 검증"""

    try:
        from gen_post_helper import build_places_cache, haversine_distance
    except ImportError:
        from apps.test.gen.gen_post_helper import build_places_cache, haversine_distance

    with fixture_app.app_context():
        print("\n" + "=" * 60)
        print("Place 캐시 검증")
        print("=" * 60)

        name_cache, coord_cache = build_places_cache()

        print(f"\n이름 캐시 크기: {len(name_cache)}개")
        print(f"좌표 캐시 크기: {len(coord_cache)}개")

        # 샘플 Place 출력
        print("\n캐시된 Place 샘플 (최대 5개):")
        for i, item in enumerate(coord_cache[:5]):
            print(f"  {item['name']}: ({item['lat']}, {item['lon']})")

        # 거리 계산 테스트
        print("\n거리 계산 테스트:")
        # 암사동 선사유적지 좌표 (37.5534, 127.1289)
        test_lat, test_lon = 37.5534, 127.1289

        distances = []
        for item in coord_cache:
            dist = haversine_distance(test_lat, test_lon, item["lat"], item["lon"])
            distances.append((item["name"], dist))

        distances.sort(key=lambda x: x[1])

        print(f"\n  테스트 좌표 ({test_lat}, {test_lon})에서 가까운 Place:")
        for name, dist in distances[:5]:
            print(f"    {name}: {dist:.0f}m")

        print("\n" + "=" * 60)
        print("✅ 캐시 검증 완료")
        print("=" * 60)
