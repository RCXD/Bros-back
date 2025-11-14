"""
데이터 생성 설정 관리
"""
import os
from pathlib import Path
from dotenv import load_dotenv


class GeneratorConfig:
    """데이터 생성을 위한 설정 클래스"""
    
    def __init__(self, use_test_env=False):
        """
        설정 초기화
        
        Args:
            use_test_env: True이면 TEST_ 접두사 변수 사용, 아니면 PROD_ 사용
        """
        # .env 파일 로드
        env_path = Path(__file__).parent / '.env'
        if env_path.exists():
            load_dotenv(dotenv_path=env_path)
        
        # 환경 접두사 결정
        self.env_prefix = 'TEST_' if use_test_env else 'PROD_'
        self.is_test = use_test_env
        
        # API 설정
        self.api_backend_url = self._get_env('API_BACKEND_URL', 'http://localhost:5000')
        
        # 데이터베이스 설정
        self.db_host = self._get_env('DB_HOST', 'localhost')
        self.db_port = self._get_env('DB_PORT', '3306')
        self.db_name = self._get_env('DB_NAME', '404found_test')
        self.db_user = self._get_env('DB_USER', 'root')
        self.db_password = self._get_env('DB_PASSWORD', '1234')
        
        # 생성 파라미터
        self.num_users = int(self._get_env('NUM_USERS', '10'))
        self.num_admins = int(self._get_env('NUM_ADMINS', '2'))
        
        # 이미지 경로
        self.profile_img_folder = self._get_env('PROFILE_IMG_FOLDER', 'apps/gen/uploads/profile_images')
        self.post_img_folder = self._get_env('POST_IMG_FOLDER', 'apps/gen/uploads/post_images')
        
        # 더미 데이터 경로
        self.dummy_data_dir = self._get_env('DUMMY_DATA_DIR', r'D:\share\dummy data')
        self.dummy_profile_img_dir = self._get_env('DUMMY_PROFILE_IMG_DIR', r'D:\share\dummy data\profile_images')
        self.dummy_post_img_dir = self._get_env('DUMMY_POST_IMG_DIR', r'D:\share\dummy data\images')
        
        # Post JSON 경로
        self.post_json_path = self._get_env('POST_JSON_PATH', 'apps/gen/data/post_data.json')
        
        # 데이터베이스 URI
        self.db_uri = f"mysql+pymysql://{self.db_user}:{self.db_password}@{self.db_host}:{self.db_port}/{self.db_name}"
    
    def _get_env(self, key, default):
        """접두사가 붙은 환경 변수 가져오기"""
        return os.getenv(f'{self.env_prefix}{key}', default)
    
    def print_config(self):
        """현재 설정 출력"""
        env_name = "테스트" if self.is_test else "프로덕션"
        print(f"\n{env_name} 환경 설정")
        print(f"  API 백엔드: {self.api_backend_url}")
        print(f"  데이터베이스: {self.db_host}:{self.db_port}/{self.db_name}")
        print(f"  사용자: {self.num_users}명, 관리자: {self.num_admins}명")
        print(f"  프로필 이미지: {self.profile_img_folder}")
        print(f"  게시글 이미지: {self.post_img_folder}")
        print(f"  Post JSON: {self.post_json_path}")
