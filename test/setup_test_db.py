"""
테스트 데이터베이스를 생성하는 설정 스크립트
테스트 실행 전에 이것을 실행하세요: python test/setup_test_db.py
"""
import pymysql

def setup_test_database():
    try:
        # 데이터베이스를 지정하지 않고 연결
        connection = pymysql.connect(
            host='localhost',
            user='root',
            password='1234',
            charset='utf8mb4'
        )
        
        with connection.cursor() as cursor:
            # 테스트 데이터베이스가 없으면 생성
            cursor.execute("CREATE DATABASE IF NOT EXISTS 404found_test CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci")
            print("✓ 테스트 데이터베이스 '404found_test' 생성/확인 완료")
        
        connection.close()
        
    except Exception as e:
        print(f"✗ 테스트 데이터베이스 생성 중 오류: {e}")
        raise

if __name__ == "__main__":
    setup_test_database()
