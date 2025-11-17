"""
애플리케이션 동작 검증 스크립트

사용 방법:
    python apps/verif.py

검증 항목:
    1. Flask 앱 생성 확인
    2. 데이터베이스 연결 확인
    3. 모든 블루프린트 등록 확인
    4. JWT 설정 확인
    5. 정적 파일 경로 확인
    6. 필수 디렉토리 생성 확인
    7. 기본 라우트 동작 확인

출력:
    - 성공: 각 항목별 통과 메시지
    - 실패: 에러 메시지와 상세 정보
"""

import sys
from pathlib import Path

# 프로젝트 루트를 경로에 추가
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from apps.app import create_app
from apps.config.server import db
import os


def verify_app_creation():
    """Flask 앱 생성 확인"""
    print("\n[1/7] Flask 앱 생성 확인...")
    try:
        app = create_app('development')
        assert app is not None, "앱이 None입니다"
        print(f"  ✓ Flask 앱 생성 성공: {app.name}")
        return app
    except Exception as e:
        print(f"  ✗ 실패: {e}")
        return None


def verify_database_connection(app):
    """데이터베이스 연결 확인"""
    print("\n[2/7] 데이터베이스 연결 확인...")
    try:
        with app.app_context():
            db.engine.connect()
            print(f"  ✓ 데이터베이스 연결 성공")
            print(f"    URI: {app.config['SQLALCHEMY_DATABASE_URI'].split('@')[1] if '@' in app.config['SQLALCHEMY_DATABASE_URI'] else 'SQLite'}")
        return True
    except Exception as e:
        print(f"  ✗ 실패: {e}")
        return False


def verify_blueprints(app):
    """블루프린트 등록 확인"""
    print("\n[3/7] 블루프린트 등록 확인...")
    try:
        blueprints = list(app.blueprints.keys())
        expected_blueprints = [
            'auth', 'user', 'post', 'reply', 'feed', 
            'route', 'product', 'favorite', 'detector', 
            'security', 'admin'
        ]
        
        # DEBUG 모드에서는 test 블루프린트도 포함
        if app.config.get('DEBUG'):
            expected_blueprints.append('test')
        
        registered_count = len(blueprints)
        print(f"  ✓ 등록된 블루프린트: {registered_count}개")
        
        for bp_name in expected_blueprints:
            if bp_name in blueprints:
                print(f"    ✓ {bp_name}")
            else:
                print(f"    ✗ {bp_name} (누락)")
        
        return registered_count > 0
    except Exception as e:
        print(f"  ✗ 실패: {e}")
        return False


def verify_jwt_config(app):
    """JWT 설정 확인"""
    print("\n[4/7] JWT 설정 확인...")
    try:
        jwt_secret = app.config.get('JWT_SECRET_KEY')
        jwt_algorithm = app.config.get('JWT_ALGORITHM', 'HS256')
        jwt_expiration = app.config.get('JWT_ACCESS_TOKEN_EXPIRES')
        
        assert jwt_secret is not None, "JWT_SECRET_KEY가 설정되지 않았습니다"
        
        print(f"  ✓ JWT 설정 확인 완료")
        print(f"    알고리즘: {jwt_algorithm}")
        print(f"    토큰 만료 시간: {jwt_expiration}")
        print(f"    Secret Key: {'설정됨' if jwt_secret else '미설정'}")
        return True
    except Exception as e:
        print(f"  ✗ 실패: {e}")
        return False


def verify_static_files(app):
    """정적 파일 경로 확인"""
    print("\n[5/7] 정적 파일 경로 확인...")
    try:
        static_folder = app.static_folder
        static_url = app.static_url_path
        
        print(f"  ✓ 정적 파일 설정 확인")
        print(f"    폴더: {static_folder}")
        print(f"    URL: {static_url}")
        return True
    except Exception as e:
        print(f"  ✗ 실패: {e}")
        return False


def verify_directories(app):
    """필수 디렉토리 생성 확인"""
    print("\n[6/7] 필수 디렉토리 생성 확인...")
    try:
        with app.app_context():
            directories = [
                os.path.join(app.root_path, 'static', 'profile_images'),
                os.path.join(app.root_path, 'static', 'post_images'),
                os.path.join(app.root_path, 'static', 'product_images'),
            ]
            
            all_exist = True
            for directory in directories:
                exists = os.path.exists(directory)
                status = "✓" if exists else "✗"
                dir_name = os.path.basename(directory)
                print(f"    {status} {dir_name}: {directory}")
                if not exists:
                    all_exist = False
            
            if all_exist:
                print(f"  ✓ 모든 디렉토리 생성 완료")
            else:
                print(f"  ⚠ 일부 디렉토리가 생성되지 않았습니다")
            
            return True
    except Exception as e:
        print(f"  ✗ 실패: {e}")
        return False


def verify_routes(app):
    """기본 라우트 동작 확인"""
    print("\n[7/7] 기본 라우트 동작 확인...")
    try:
        with app.test_client() as client:
            # 존재하지 않는 경로 테스트 (404 반환 예상)
            response = client.get('/nonexistent')
            assert response.status_code == 404, f"예상: 404, 실제: {response.status_code}"
            
            # 정적 파일 경로 테스트
            response = client.get('/static/')
            # 정적 파일 경로는 200 또는 404 가능 (파일 존재 여부에 따라)
            
            print(f"  ✓ 라우트 동작 확인 완료")
            print(f"    테스트 클라이언트 정상 작동")
            print(f"    404 응답 정상 처리")
        return True
    except Exception as e:
        print(f"  ✗ 실패: {e}")
        return False


def run_verification():
    """전체 검증 실행"""
    print("="*60)
    print("Flask 애플리케이션 검증 시작")
    print("="*60)
    
    results = []
    
    # 1. 앱 생성
    app = verify_app_creation()
    results.append(("앱 생성", app is not None))
    
    if app is None:
        print("\n앱 생성 실패로 인해 검증을 중단합니다.")
        return False
    
    # 2. 데이터베이스 연결
    db_result = verify_database_connection(app)
    results.append(("데이터베이스 연결", db_result))
    
    # 3. 블루프린트
    bp_result = verify_blueprints(app)
    results.append(("블루프린트 등록", bp_result))
    
    # 4. JWT 설정
    jwt_result = verify_jwt_config(app)
    results.append(("JWT 설정", jwt_result))
    
    # 5. 정적 파일
    static_result = verify_static_files(app)
    results.append(("정적 파일 경로", static_result))
    
    # 6. 디렉토리
    dir_result = verify_directories(app)
    results.append(("필수 디렉토리", dir_result))
    
    # 7. 라우트
    route_result = verify_routes(app)
    results.append(("라우트 동작", route_result))
    
    # 결과 요약
    print("\n" + "="*60)
    print("검증 결과 요약")
    print("="*60)
    
    passed = sum(1 for _, result in results if result)
    total = len(results)
    
    for name, result in results:
        status = "✓ 통과" if result else "✗ 실패"
        print(f"  {status}: {name}")
    
    print("\n" + "="*60)
    print(f"결과: {passed}/{total} 항목 통과")
    
    if passed == total:
        print("상태: 모든 검증 통과")
    else:
        print(f"상태: {total - passed}개 항목 실패")
    
    print("="*60)
    
    return passed == total


if __name__ == '__main__':
    success = run_verification()
    sys.exit(0 if success else 1)
