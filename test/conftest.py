import os
import shutil
import pytest
import warnings
from pathlib import Path
from dotenv import load_dotenv
from app import create_app
from app.extensions import db
from app.config import Config

# .gen.env 파일 로드 (test/.gen.env)
env_path = Path(__file__).parent / '.gen.env'
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
    parser.addoption(
        "--reset-prev-data",
        action="store_true",
        default=False,
        help="데이터 생성 전 기존 데이터를 모두 삭제합니다"
    )
    parser.addoption(
        "--legacy",
        action="store_true",
        default=False,
        help="레거시 API 엔드포인트 사용 (기본값: V1 API)"
    )


@pytest.fixture(scope="session")
def fixture_app(request):
    # 명령줄 옵션 확인
    keep_data = request.config.getoption("--keep-data")
    clean_data = request.config.getoption("--clean-data")
    use_test_env = request.config.getoption("--use-test-env")
    reset_prev_data = request.config.getoption("--reset-prev-data")
    use_legacy_api = request.config.getoption("--legacy")
    
    # --keep-data가 명시되면 True, --clean-data가 명시되면 False, 둘 다 없으면 False (기본값)
    if keep_data:
        keep_generated_data = True
    else:
        keep_generated_data = False
    
    # API 버전 설정
    api_version = 'legacy' if use_legacy_api else 'v1'
    
    # 환경에 따라 .env 설정 읽기
    if use_test_env:
        # 테스트 환경
        env_prefix = 'TEST_'
    else:
        # 프로덕션 환경
        env_prefix = 'PROD_'
    
    # Verbosity 설정
    verbosity = int(os.getenv(f'{env_prefix}VERBOSITY', '1'))
    
    # 로거 초기화
    from test.database.logger import init_logger
    log = init_logger(verbosity)
    
    # 환경 정보 출력
    if verbosity >= 1:
        env_name = "테스트" if use_test_env else "프로덕션"
        print(f"\n{env_name} 환경 (API: {api_version.upper()}, Verbosity: {verbosity})")
    
    # .env 파일에서 설정 읽기 (환경별 접두사 사용)
    api_backend_url = os.getenv(f'{env_prefix}API_BACKEND_URL', 'http://localhost:5000')
    db_host = os.getenv(f'{env_prefix}DB_HOST', 'localhost')
    db_port = os.getenv(f'{env_prefix}DB_PORT', '3306')
    db_name = os.getenv(f'{env_prefix}DB_NAME', '404found_test')
    db_user = os.getenv(f'{env_prefix}DB_USER', 'root')
    db_password = os.getenv(f'{env_prefix}DB_PASSWORD', '1234')
    
    # 사용자 생성 수
    num_users = int(os.getenv(f'{env_prefix}NUM_USERS', '10'))
    num_admins = int(os.getenv(f'{env_prefix}NUM_ADMINS', '2'))
    
    # 이미지 경로 설정
    profile_folder = os.getenv(f'{env_prefix}PROFILE_IMG_FOLDER', 'test/uploads/profile_images')
    post_folder = os.getenv(f'{env_prefix}POST_IMG_FOLDER', 'test/uploads/post_images')
    dummy_data_dir = os.getenv(f'{env_prefix}DUMMY_DATA_DIR', r'D:\share\dummy data')
    dummy_profile_img_dir = os.getenv(f'{env_prefix}DUMMY_PROFILE_IMG_DIR', r'D:\share\dummy data\profile_images')
    dummy_post_img_dir = os.getenv(f'{env_prefix}DUMMY_POST_IMG_DIR', r'D:\share\dummy data\images')
    
    # Post JSON 경로
    post_json_path = os.getenv(f'{env_prefix}POST_JSON_PATH', 'test/database/post_data.json')
    
    # 데이터베이스 URI 구성
    db_uri = f"mysql+pymysql://{db_user}:{db_password}@{db_host}:{db_port}/{db_name}"
    
    # 앱 생성 전 설정 오버라이드
    Config.TESTING = True
    Config.KEEP_GENERATED_DATA = keep_generated_data
    Config.RESET_PREV_DATA = reset_prev_data
    Config.API_VERSION = api_version
    Config.VERBOSITY = verbosity
    Config.PROFILE_IMG_UPLOAD_FOLDER = profile_folder
    Config.POST_IMG_UPLOAD_FOLDER = post_folder
    Config.DUMMY_DATA_DIR = dummy_data_dir
    Config.DUMMY_PROFILE_IMG_DIR = dummy_profile_img_dir
    Config.DUMMY_POST_IMG_DIR = dummy_post_img_dir
    Config.SQLALCHEMY_DATABASE_URI = db_uri
    Config.SQLALCHEMY_ECHO = False  # 테스트 중 출력 소음 감소
    Config.API_BACKEND_URL = api_backend_url
    Config.NUM_USERS = num_users
    Config.NUM_ADMINS = num_admins
    Config.POST_JSON_PATH = post_json_path
    
    # 설정 정보 출력 (verbosity에 따라)
    if verbosity >= 2:
        print(f"  API 백엔드: {api_backend_url}")
        print(f"  API 버전: {api_version.upper()}")
        print(f"  생성할 사용자: {num_users}명 (관리자: {num_admins}명)")
        print(f"  프로필 이미지: {profile_folder}")
        print(f"  게시글 이미지: {post_folder}")
        print(f"  더미 데이터: {dummy_data_dir}")
        print(f"  Post JSON: {post_json_path}")
        print(f"  데이터베이스: {db_uri.split('@')[1]}")
    elif verbosity >= 1:
        print(f"  API: {api_backend_url}, DB: {db_name}, Users: {num_users}+{num_admins}")
    
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
