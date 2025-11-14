import os
import shutil
import pytest
from app import create_app
from app.extensions import db
from app.config import Config

from app.models.user import User, OauthType, AccountType
from app.models.image import Image
from app.models.post import Post
from app.models.reply import Reply

from werkzeug.security import check_password_hash, generate_password_hash


@pytest.fixture(scope="session")
def fixture_app():
    # 앱 생성 전 설정 오버라이드 - 별도의 테스트 데이터베이스 사용
    Config.TESTING = True
    Config.PROFILE_IMG_UPLOAD_FOLDER = "test/uploads/profile_images"
    Config.POST_IMG_UPLOAD_FOLDER = "test/uploads/post_images"
    Config.SQLALCHEMY_DATABASE_URI = "mysql+pymysql://root:1234@localhost:3306/404found_test"
    Config.SQLALCHEMY_ECHO = False  # 테스트 중 출력 소음 감소

    app = create_app()
    
    with app.app_context():
        # 테스트용 디렉토리 만들기
        os.makedirs(app.config["PROFILE_IMG_UPLOAD_FOLDER"], exist_ok=True)
        os.makedirs(app.config["POST_IMG_UPLOAD_FOLDER"], exist_ok=True)
        
        # 모든 테이블 생성
        db.create_all()

    yield app
    
    # 정리: 모든 테스트 후 정리
    with app.app_context():
        db.session.remove()
        # db.drop_all()

    # 테스트용 디렉토리 삭제
    if os.path.exists(app.config['PROFILE_IMG_UPLOAD_FOLDER']):
        shutil.rmtree(app.config['PROFILE_IMG_UPLOAD_FOLDER'])
    if os.path.exists(app.config['POST_IMG_UPLOAD_FOLDER']):
        shutil.rmtree(app.config['POST_IMG_UPLOAD_FOLDER'])


@pytest.fixture(autouse=True)
def clean_db(fixture_app, request):
    """테스트 간 데이터베이스 정리하지만 스키마는 유지"""
    # 데이터 생성기 테스트는 정리 건너뛰기 ('no_cleanup'으로 마크된 경우)
    if 'no_cleanup' in request.keywords:
        yield
        return
    
    yield
    with fixture_app.app_context():
        # 데이터는 지우지만 테이블은 삭제하지 않음
        db.session.rollback()
        for table in reversed(db.metadata.sorted_tables):
            db.session.execute(table.delete())
        db.session.commit()


@pytest.fixture
def client(fixture_app):
    return fixture_app.test_client()
