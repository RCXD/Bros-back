"""
데이터베이스의 모든 데이터를 삭제하는 스크립트
테이블 구조는 유지하고 데이터만 삭제합니다
"""
import pytest
from app.extensions import db


@pytest.mark.no_cleanup
def test_clear_database(fixture_app):
    """데이터베이스의 모든 데이터 삭제 (테이블 구조 유지)"""
    
    with fixture_app.app_context():
        print("\n" + "="*60)
        print("데이터베이스 정리 중")
        print("="*60)
        
        # 외래 키 제약 조건 일시 비활성화
        db.session.execute(db.text("SET FOREIGN_KEY_CHECKS = 0"))
        
        # 모든 테이블의 데이터 삭제
        print("\n🗑️  모든 테이블 데이터 삭제 중...")
        deleted_tables = []
        
        for table in reversed(db.metadata.sorted_tables):
            result = db.session.execute(table.delete())
            if result.rowcount > 0:
                deleted_tables.append(f"  - {table.name}: {result.rowcount}개 레코드 삭제")
        
        # 외래 키 제약 조건 재활성화
        db.session.execute(db.text("SET FOREIGN_KEY_CHECKS = 1"))
        db.session.commit()
        
        if deleted_tables:
            print("\n삭제된 데이터:")
            for msg in deleted_tables:
                print(msg)
        else:
            print("\n  ℹ️  삭제할 데이터가 없습니다.")
        
        print("\n" + "="*60)
        print("✅ 데이터베이스 정리 완료!")
        print("="*60 + "\n")


if __name__ == "__main__":
    print("pytest를 사용하여 실행하세요:")
    print("pytest test/database/clear_db.py -v -s --use-test-env")
    print("또는")
    print("pytest test/database/clear_db.py -v -s  # 프로덕션 DB")
