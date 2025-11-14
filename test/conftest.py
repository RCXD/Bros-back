import os
import shutil
import pytest
import warnings
from pathlib import Path
from dotenv import load_dotenv
from app import create_app
from app.extensions import db
from app.config import Config

# .env 파일 로드
env_path = Path(__file__).parent.parent / '.env'
load_dotenv(dotenv_path=env_path)

# SQLAlchemy 경고 억제
warnings.filterwarnings('ignore', category=DeprecationWarning)
warnings.filterwarnings('ignore', message='.*relationship.*')
warnings.filterwarnings('ignore', message='.*SAWarning.*')


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
    parser.addoption(
        "--use-test-env",
        action="store_true",
        default=False,
        help="테스트 환경 사용 (test/uploads, localhost DB)"
    )


@pytest.fixture(scope="session")
def fixture_app(request):
    # 명령줄 옵션 확인
    keep_data = request.config.getoption("--keep-data")
    clean_data = request.config.getoption("--clean-data")
    use_test_env = request.config.getoption("--use-test-env")
    
    # --keep-data가 명시되면 True, --clean-data가 명시되면 False, 둘 다 없으면 False (기본값)
    if keep_data:
        keep_generated_data = True
    else:
        keep_generated_data = False
    
    # .env 파일에서 설정 읽기
    api_backend_url = os.getenv('API_BACKEND_URL', 'http://localhost:5000')
    db_host = os.getenv('DB_HOST', 'localhost')
    db_port = os.getenv('DB_PORT', '3306')
    db_name = os.getenv('DB_NAME', '404found_test')
    db_user = os.getenv('DB_USER', 'root')
    db_password = os.getenv('DB_PASSWORD', '1234')
    
    # 데이터베이스 URI 구성
    db_uri = f"mysql+pymysql://{db_user}:{db_password}@{db_host}:{db_port}/{db_name}"
    
    # --use-test-env 옵션에 따라 환경 설정
    if use_test_env:
        # 테스트 환경
        profile_folder = "test/uploads/profile_images"
        post_folder = "test/uploads/post_images"
        print("\n🔧 테스트 환경 사용")
    else:
        # 프로덕션 모드
        profile_folder = "static/profile_images"
        post_folder = "static/post_images"
        print("\n🚀 프로덕션 환경 사용")
    
    # 앱 생성 전 설정 오버라이드 - 별도의 테스트 데이터베이스 사용
    Config.TESTING = True
    Config.KEEP_GENERATED_DATA = keep_generated_data
    Config.PROFILE_IMG_UPLOAD_FOLDER = profile_folder
    Config.POST_IMG_UPLOAD_FOLDER = post_folder
    Config.DUMMY_DATA_DIR = r"D:\share\dummy data"
    Config.DUMMY_PROFILE_IMG_DIR = r"D:\share\dummy data\profile_images"
    Config.DUMMY_POST_IMG_DIR = r"D:\share\dummy data\images"
    Config.SQLALCHEMY_DATABASE_URI = db_uri
    Config.SQLALCHEMY_ECHO = False  # 테스트 중 출력 소음 감소
    Config.API_BACKEND_URL = api_backend_url  # API 백엔드 URL 추가
    
    print(f"  🌐 API 백엔드: {api_backend_url}")
    print(f"  📁 프로필 이미지: {profile_folder}")
    print(f"  📁 게시글 이미지: {post_folder}")
    print(f"  💾 데이터베이스: {db_uri.split('@')[1]}")
    
    if keep_generated_data:
        print(f"  💾 데이터 유지: 예 (테스트 후 데이터 유지)\n")
    else:
        print(f"  🗑️  데이터 유지: 아니오 (테스트 후 삭제)\n")

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
            
            # 데이터를 유지하지 않는 경우에만 업로드 디렉토리 삭제
            if os.path.exists(app.config['PROFILE_IMG_UPLOAD_FOLDER']):
                shutil.rmtree(app.config['PROFILE_IMG_UPLOAD_FOLDER'])
                print(f"  🗑️  삭제: {app.config['PROFILE_IMG_UPLOAD_FOLDER']}")
            if os.path.exists(app.config['POST_IMG_UPLOAD_FOLDER']):
                shutil.rmtree(app.config['POST_IMG_UPLOAD_FOLDER'])
                print(f"  🗑️  삭제: {app.config['POST_IMG_UPLOAD_FOLDER']}")
        else:
            print("\n💾 KEEP_GENERATED_DATA=True: 생성된 데이터가 데이터베이스에 유지됩니다.")
            print(f"  📁 프로필 이미지 유지: {app.config['PROFILE_IMG_UPLOAD_FOLDER']}")
            print(f"  📁 게시글 이미지 유지: {app.config['POST_IMG_UPLOAD_FOLDER']}")
            db.session.remove()


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
