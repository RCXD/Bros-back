"""
데이터베이스의 모든 데이터를 삭제하는 스크립트
테이블 구조는 유지하고 데이터만 삭제합니다
"""

import pytest
from apps.config.server import db

try:
    from logger import get_logger
except ImportError:
    from apps.common.logger import get_logger


@pytest.mark.no_cleanup
def test_clear_database(fixture_app):
    """데이터베이스의 모든 데이터 삭제 (테이블 구조 유지)"""

    log = get_logger()

    with fixture_app.app_context():
        verbosity = fixture_app.config.get("VERBOSITY", 1)

        log.info("\n[0/5] 데이터베이스 정리")

        # 외래 키 제약 조건 일시 비활성화
        db.session.execute(db.text("SET FOREIGN_KEY_CHECKS = 0"))

        # 모든 테이블의 데이터 삭제
        log.debug("  모든 테이블 데이터 삭제 중...")
        deleted_count = 0

        for table in reversed(db.metadata.sorted_tables):
            result = db.session.execute(table.delete())
            if result.rowcount > 0:
                deleted_count += result.rowcount
                log.debug(f"    {table.name}: {result.rowcount}개")

        # 외래 키 제약 조건 재활성화
        db.session.execute(db.text("SET FOREIGN_KEY_CHECKS = 1"))
        db.session.commit()

        if deleted_count > 0:
            log.success(f"  {deleted_count}개 레코드 삭제 완료")
        else:
            log.info("  삭제할 데이터 없음")


if __name__ == "__main__":
    print("pytest를 사용하여 실행하세요:")
    print("pytest apps/test/gen/clear_db.py -v -s --use-test-env")
    print("또는")
    print("pytest apps/test/gen/clear_db.py -v -s  # 프로덕션 DB")
