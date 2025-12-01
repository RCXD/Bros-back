"""
데이터베이스의 모든 테이블을 삭제하는 스크립트
--drop-tables 옵션으로 테이블 구조까지 삭제 가능
"""

import pytest
from apps.config.server import db

try:
    from logger import get_logger
except ImportError:
    from apps.common.logger import get_logger


def clear_database(app, drop_tables=False):
    """
    데이터베이스 정리 (직접 호출용)

    Args:
        app: Flask 앱 인스턴스
        drop_tables: True면 테이블 삭제, False면 데이터만 삭제
    """
    log = get_logger()

    with app.app_context():
        if drop_tables:
            log.info("\n[0/5] 데이터베이스 테이블 삭제 (DROP)")
            _drop_all_tables(log)
        else:
            log.info("\n[0/5] 데이터베이스 데이터 정리 (TRUNCATE)")
            _truncate_all_tables(log)

        # 이미지 폴더 초기화
        _clean_image_folders(log)


@pytest.mark.no_cleanup
def test_clear_database(fixture_app, request):
    """pytest용 테스트 함수"""

    # --drop-tables 옵션 확인
    try:
        drop_tables = request.config.getoption("--drop-tables", default=False)
    except (AttributeError, ValueError):
        drop_tables = False

    clear_database(fixture_app, drop_tables=drop_tables)


def _drop_all_tables(log):
    """모든 테이블을 DROP으로 삭제"""
    # 외래 키 제약 조건 일시 비활성화
    db.session.execute(db.text("SET FOREIGN_KEY_CHECKS = 0"))

    # 현재 데이터베이스의 모든 테이블 조회
    result = db.session.execute(
        db.text(
            "SELECT table_name FROM information_schema.tables "
            "WHERE table_schema = DATABASE() AND table_type = 'BASE TABLE'"
        )
    )
    tables = [row[0] for row in result.fetchall()]

    if not tables:
        log.info("  삭제할 테이블 없음")
        db.session.execute(db.text("SET FOREIGN_KEY_CHECKS = 1"))
        return

    log.info(f"  총 {len(tables)}개 테이블 발견")

    dropped_count = 0
    for table_name in tables:
        try:
            db.session.execute(db.text(f"DROP TABLE IF EXISTS `{table_name}`"))
            dropped_count += 1
            log.debug(f"    DROP: {table_name}")
        except Exception as e:
            log.warning(f"    [!] {table_name} 삭제 실패: {e}")

    # 외래 키 제약 조건 재활성화
    db.session.execute(db.text("SET FOREIGN_KEY_CHECKS = 1"))
    db.session.commit()

    log.success(f"  {dropped_count}개 테이블 삭제 완료")


def _truncate_all_tables(log):
    """모든 테이블의 데이터만 삭제 (테이블 구조 유지)"""
    # 외래 키 제약 조건 일시 비활성화
    db.session.execute(db.text("SET FOREIGN_KEY_CHECKS = 0"))

    # 현재 데이터베이스의 모든 테이블 조회 (SQLAlchemy 메타데이터 대신 직접 조회)
    result = db.session.execute(
        db.text(
            "SELECT table_name FROM information_schema.tables "
            "WHERE table_schema = DATABASE() AND table_type = 'BASE TABLE'"
        )
    )
    tables = [row[0] for row in result.fetchall()]

    log.debug("  모든 테이블 데이터 삭제 중...")
    deleted_count = 0

    for table_name in tables:
        try:
            # TRUNCATE로 빠르게 삭제
            db.session.execute(db.text(f"TRUNCATE TABLE `{table_name}`"))
            log.debug(f"    TRUNCATE: {table_name}")
            deleted_count += 1
        except Exception as e:
            log.warning(f"    [!] {table_name} 삭제 실패: {e}")

    # 외래 키 제약 조건 재활성화
    db.session.execute(db.text("SET FOREIGN_KEY_CHECKS = 1"))
    db.session.commit()

    if deleted_count > 0:
        log.success(f"  {deleted_count}개 테이블 데이터 삭제 완료")
    else:
        log.info("  삭제할 데이터 없음")


def _clean_image_folders(log):
    """이미지 폴더 초기화"""
    import shutil
    import os

    image_folders = [
        "apps/static/post_images",
        "apps/static/profile_images",
        "apps/static/product_images",
    ]

    for folder in image_folders:
        folder_path = os.path.join(os.getcwd(), folder)
        if os.path.exists(folder_path):
            try:
                shutil.rmtree(folder_path)
                log.info(f"  [DELETE] 삭제: {folder}")
            except Exception as e:
                log.warning(f"  [!] {folder} 삭제 실패: {e}")
        else:
            log.debug(f"  [SKIP] {folder} 폴더 없음")


def pytest_addoption(parser):
    """pytest 커맨드라인 옵션 추가"""
    try:
        parser.addoption(
            "--drop-tables",
            action="store_true",
            default=False,
            help="테이블 구조까지 완전 삭제 (DROP TABLE)",
        )
    except ValueError:
        # 이미 옵션이 등록된 경우 무시
        pass


if __name__ == "__main__":
    print("pytest를 사용하여 실행하세요:")
    print()
    print("데이터만 삭제 (테이블 구조 유지):")
    print("  pytest apps/test/gen/clear_db.py -v -s")
    print()
    print("테이블까지 완전 삭제:")
    print("  pytest apps/test/gen/clear_db.py -v -s --drop-tables")
    print()
    print("테스트 환경 사용:")
    print("  pytest apps/test/gen/clear_db.py -v -s --use-test-env")
    print("  pytest apps/test/gen/clear_db.py -v -s --use-test-env --drop-tables")
