import os
import shutil
import pytest
from app import create_app
from app.extensions import db
from app.config import Config


def pytest_addoption(parser):
    """pytest 명령줄 옵션 추가"""
    parser.addoption(
        "--keep-data",
        action="store_true",
        default=False,
        help="생성된 테스트 데이터를 데이터베이스에 유지합니다"
    )
    parser.addoption(
        "--clean-data",
        action="store_true",
        default=False,
        help="테스트 후 모든 데이터를 정리합니다 (기본 동작)"
    )


@pytest.fixture(scope="session")
def fixture_app(request):
    # 명령줄 옵션 확인
    keep_data = request.config.getoption("--keep-data")
    clean_data = request.config.getoption("--clean-data")
    
    # --clean-data가 명시되면 False, 아니면 --keep-data 값 또는 기본값 True 사용
    if clean_data:
        keep_generated_data = False
    elif keep_data:
        keep_generated_data = True
    else:
        # 기본값: True (기존 동작 유지)
        keep_generated_data = True
    
    # 앱 생성 전 설정 오버라이드 - 별도의 테스트 데이터베이스 사용
    Config.TESTING = True
    Config.KEEP_GENERATED_DATA = keep_generated_data
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
        # KEEP_GENERATED_DATA가 True면 데이터와 테이블 유지
        if not app.config.get('KEEP_GENERATED_DATA', False):
            try:
                # 외래 키 제약 조건을 일시적으로 비활성화
                db.session.execute(db.text("SET FOREIGN_KEY_CHECKS = 0"))
                db.session.commit()
                db.drop_all()
                db.session.execute(db.text("SET FOREIGN_KEY_CHECKS = 1"))
                db.session.commit()
            except Exception as e:
                print(f"Warning during cleanup: {e}")
            finally:
                db.session.remove()
        else:
            print("\n💾 KEEP_GENERATED_DATA=True: 생성된 데이터가 데이터베이스에 유지됩니다.")
            db.session.remove()

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
    
    # KEEP_GENERATED_DATA가 True면 데이터 정리하지 않음
    if fixture_app.config.get('KEEP_GENERATED_DATA', False):
        yield
        return
    
    yield
    with fixture_app.app_context():
        # 데이터는 지우지만 테이블은 삭제하지 않음
        db.session.rollback()
        # 외래 키 제약 조건을 일시적으로 비활성화
        db.session.execute(db.text("SET FOREIGN_KEY_CHECKS = 0"))
        for table in reversed(db.metadata.sorted_tables):
            db.session.execute(table.delete())
        db.session.execute(db.text("SET FOREIGN_KEY_CHECKS = 1"))
        db.session.commit()


@pytest.fixture
def client(fixture_app):
    return fixture_app.test_client()
