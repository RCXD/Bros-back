"""
Flask 애플리케이션 팩토리
모듈형 블루프린트 구조로 리팩토링된 아키텍처
"""

# 경로 설정: apps 디렉토리가 인식되도록 프로젝트 루트를 경로에 추가
import sys
from pathlib import Path

# 프로젝트 루트 디렉토리를 sys.path에 추가
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from flask import Flask
from apps.config.common import config
from apps.config.server import db, migrate, cors, jwt
from apps.common.jwt_handlers import register_jwt_handlers
from apps.cosmetic.seed import seed_cosmetics
import os


def create_app(config_name="default"):
    """
    애플리케이션 팩토리 패턴

    Args:
        config_name: 설정 이름 (development, production, test)

    Returns:
        Flask 애플리케이션 인스턴스
    """
    app = Flask(__name__)

    # 설정 로드
    app.config.from_object(config[config_name])

    app.cli.add_command(seed_cosmetics)

    # 정적 파일 설정 (환경 변수에서 가져오기)
    app.static_folder = app.config.get("STATIC_FOLDER", "static")
    app.static_url_path = app.config.get("STATIC_URL_PATH", "/static")

    # 확장 기능 초기화
    db.init_app(app)
    migrate.init_app(app, db)
    cors.init_app(app, origins=app.config["CORS_ORIGINS"])
    jwt.init_app(app)

    # JWT 핸들러 등록
    register_jwt_handlers(jwt)

    # HTTP 인터셉터 및 로깅 설정
    from apps.common.interceptors import register_interceptors, setup_logging

    setup_logging(app)
    register_interceptors(app)

    # 모든 모델 import (Flask-Migrate가 인식하도록)
    with app.app_context():
        import_all_models()

    # 블루프린트 등록
    register_blueprints(app)

    # 업로드 디렉토리 생성
    with app.app_context():
        create_directories(app)

    return app


def import_all_models():
    """모든 모델을 import하여 Flask-Migrate가 인식하도록 함"""
    from apps.auth.models import User, OauthType, AccountType
    from apps.post.models import Post, PostLike, Category
    from apps.image.models import Image
    from apps.reply.models import Reply, ReplyLike
    from apps.user.models import Follow, Friend
    from apps.mention.models import Mention
    from apps.notification.models import Notification, NotificationType
    from apps.favorite.models import Favorite, FavoriteType
    from apps.feed.models import FeedItem
    from apps.product.models import Product
    from apps.report.models import Report
    from apps.report.models import ReportType
    from apps.place.models import Place

    # 필요한 다른 모델들도 여기에 추가


def register_blueprints(app):
    """모든 애플리케이션 블루프린트 등록"""

    # 인증 모듈
    from apps.auth.views import bp as auth_bp

    app.register_blueprint(auth_bp, url_prefix="/auth")

    # 사용자 모듈
    from apps.user.views import bp as user_bp

    app.register_blueprint(user_bp, url_prefix="/user")

    # 게시물 모듈
    from apps.post.views import bp as post_bp

    app.register_blueprint(post_bp, url_prefix="/post")

    # 댓글 모듈
    from apps.reply.views import bp as reply_bp

    app.register_blueprint(reply_bp, url_prefix="/reply")

    # 피드 모듈
    from apps.feed.views import bp as feed_bp

    app.register_blueprint(feed_bp, url_prefix="/feed")

    # 경로 모듈
    from apps.route.views import bp as route_bp

    app.register_blueprint(route_bp, url_prefix="/route")

    # 즐겨찾기 장소 모듈
    from apps.place.views import bp as place_bp

    app.register_blueprint(place_bp, url_prefix="/place")

    # 코스메틱 모듈
    from apps.cosmetic.views import bp as cosmetic_bp

    app.register_blueprint(cosmetic_bp, url_prefix="/cosmetic")

    # 제품 모듈
    from apps.product.views import bp as product_bp

    app.register_blueprint(product_bp, url_prefix="/product")

    # 이미지 모듈
    from apps.image.views import bp as image_bp

    app.register_blueprint(image_bp, url_prefix="/image")

    # 즐겨찾기 모듈
    from apps.favorite.views import bp as favorite_bp

    app.register_blueprint(favorite_bp, url_prefix="/favorite")

    # 알림 모듈
    from apps.notification.views import bp as notification_bp

    app.register_blueprint(notification_bp, url_prefix="/notification")

    # 멘션 모듈
    from apps.mention.views import bp as mention_bp

    app.register_blueprint(mention_bp, url_prefix="/mention")

    # 신고 모듈
    from apps.report.views import bp as report_bp

    app.register_blueprint(report_bp, url_prefix="/report")

    # 로드뷰 모듈
    from apps.roadview.views import bp as roadview_bp, init_roadview_models

    app.register_blueprint(roadview_bp, url_prefix="/roadview")
    init_roadview_models(db)  # Initialize roadview models

    # 감지기 모듈
    # from apps.detector.views import bp as detector_bp
    # app.register_blueprint(detector_bp, url_prefix="/detector")

    # 보안 모듈 (주석 처리 - security 모듈이 비활성화됨)
    # from apps.security.views import bp as security_bp
    # app.register_blueprint(security_bp, url_prefix="/security")

    # 관리자 모듈
    from apps.admin.views import bp as admin_bp

    app.register_blueprint(admin_bp, url_prefix="/admin")

    # 테스트 모듈 (개발 환경인 경우)
    # if app.config.get('DEBUG'):
    #     from apps.test.views import bp as test_bp
    #     app.register_blueprint(test_bp, url_prefix="/test")


def create_directories(app):
    """파일 업로드를 위한 필수 디렉토리 생성"""
    directories = [
        os.path.join(app.root_path, "static", "profile_images"),
        os.path.join(app.root_path, "static", "post_images"),
        os.path.join(app.root_path, "static", "product_images"),
        os.path.join(app.root_path, "static", "cosmetic_overlays"),
        os.path.join(app.root_path, "static", "profile_images"),
        os.path.join(app.root_path, "static", "post_images"),
        os.path.join(app.root_path, "static", "product_images"),
        os.path.join(app.root_path, "static", "cosmetic_overlays"),
    ]

    for directory in directories:
        os.makedirs(directory, exist_ok=True)


if __name__ == "__main__":
    import os
    import argparse
    from dotenv import load_dotenv

    # 커맨드 라인 인자 파싱
    parser = argparse.ArgumentParser(description="Flask 애플리케이션 서버 실행")
    parser.add_argument(
        "--local", action="store_true", help="로컬 개발 환경 사용 (.env.local)"
    )
    parser.add_argument(
        "--prod", action="store_true", help="프로덕션 환경 사용 (.env.production)"
    )
    parser.add_argument("--debug", action="store_true", help="디버그 모드 강제 활성화")
    args = parser.parse_args()

    # 환경 파일 선택 및 로드
    if args.prod:
        env_file = ".env.production"
        config_name = "production"
        print(f" * 프로덕션 환경으로 시작합니다: {env_file}")
    elif args.local:
        env_file = ".env.local"
        config_name = "development"
        print(f" * 로컬 개발 환경으로 시작합니다: {env_file}")
    else:
        # 기본값: .env.local 또는 .env 사용
        env_file = ".env.local" if os.path.exists(".env.local") else ".env"
        config_name = "development"
        print(f" * 기본 환경으로 시작합니다: {env_file}")

    # 환경 변수 로드
    if os.path.exists(env_file):
        load_dotenv(env_file)
        print(f" * 환경 변수 로드 완료: {env_file}")
    else:
        print(f" * 경고: {env_file} 파일을 찾을 수 없습니다. 기본값을 사용합니다.")

    # 앱 생성
    app = create_app(config_name)

    # 서버 설정 가져오기
    host = os.getenv("FLASK_HOST", "0.0.0.0")
    port = int(os.getenv("FLASK_PORT", 8001))
    debug = os.getenv("FLASK_DEBUG", "False").lower() in ("true", "1", "yes", "on")

    # 커맨드 라인에서 디버그 모드 강제 활성화
    if args.debug:
        debug = True
        print(" * 디버그 모드가 커맨드 라인 옵션으로 활성화되었습니다.")

    # 서버 정보 출력
    print(f" * 서버 호스팅: http://{host}:{port}")
    print(f' * 디버그 모드: {"활성화" if debug else "비활성화"}')
    print(f" * 설정 프로필: {config_name}")

    # 서버 실행
    app.run(host=host, port=port, debug=debug)
