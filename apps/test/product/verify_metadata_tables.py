"""
Utility to verify metadata tables exist after migration.

Usage:
    python apps/test/product/verify_metadata_tables.py
"""

import sys
import os

# 프로젝트 루트를 sys.path에 추가
sys.path.insert(
    0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", ".."))
)

from flask import Flask
from sqlalchemy import inspect, text

from apps.config.server import db


REQUIRED_TABLES = {
    "product_sellers": {"seller_id", "name", "slug", "logo_filename"},
    "product_malls": {"mall_id", "name", "slug", "logo_filename"},
    "product_brands": {"brand_id", "name", "slug", "logo_filename"},
}


def create_minimal_app():
    """최소한의 Flask 앱 생성 (DB 연결만)"""
    app = Flask(__name__)

    # DB 설정 로드
    from apps.config.common import Config

    app.config["SQLALCHEMY_DATABASE_URI"] = Config.SQLALCHEMY_DATABASE_URI
    app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False

    db.init_app(app)
    return app


def create_tables_if_missing(inspector):
    """누락된 테이블 생성"""
    existing_tables = set(inspector.get_table_names())
    missing = set(REQUIRED_TABLES.keys()) - existing_tables

    if missing:
        print(f"Creating missing tables: {', '.join(sorted(missing))}")
        # 모델 임포트 후 테이블 생성
        from apps.product.models import ProductSeller, ProductMall, ProductBrand

        db.create_all()
        print("Tables created successfully.")
        return True
    return False


def verify_tables(inspector):
    """테이블 및 컬럼 검증"""
    existing_tables = set(inspector.get_table_names())

    missing = set(REQUIRED_TABLES.keys()) - existing_tables
    if missing:
        raise SystemExit(f"Missing tables: {', '.join(sorted(missing))}")

    for table_name, required_columns in REQUIRED_TABLES.items():
        columns = {col["name"] for col in inspector.get_columns(table_name)}
        diff = required_columns - columns
        if diff:
            raise SystemExit(f"{table_name} missing columns: {', '.join(sorted(diff))}")

    print("✓ All metadata tables and required columns are present.")


def show_table_stats():
    """테이블 행 수 출력"""
    print("\n=== Table Statistics ===")
    for table_name in REQUIRED_TABLES.keys():
        result = db.session.execute(text(f"SELECT COUNT(*) FROM {table_name}"))
        count = result.scalar()
        print(f"  {table_name}: {count} rows")


def run():
    app = create_minimal_app()

    with app.app_context():
        inspector = inspect(db.engine)

        # 테이블 생성 시도
        created = create_tables_if_missing(inspector)
        if created:
            # 새로 생성된 경우 inspector 갱신
            inspector = inspect(db.engine)

        # 검증
        verify_tables(inspector)

        # 통계 출력
        show_table_stats()

        print("\n✓ Metadata table verification complete.")


if __name__ == "__main__":
    run()
