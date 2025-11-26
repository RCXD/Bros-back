"""
products 테이블에 seller_id, mall_id, brand_id FK 컬럼 추가 마이그레이션

Usage:
    python apps/test/product/migrate_product_fk.py
"""

import sys
import os

sys.path.insert(
    0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", ".."))
)

from flask import Flask
from sqlalchemy import text, inspect

from apps.config.server import db


def create_minimal_app():
    """최소한의 Flask 앱 생성 (DB 연결만)"""
    app = Flask(__name__)

    from apps.config.common import Config

    app.config["SQLALCHEMY_DATABASE_URI"] = Config.SQLALCHEMY_DATABASE_URI
    app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False

    db.init_app(app)
    return app


def column_exists(inspector, table_name, column_name):
    """테이블에 컬럼이 존재하는지 확인"""
    columns = {col["name"] for col in inspector.get_columns(table_name)}
    return column_name in columns


def run():
    app = create_minimal_app()

    with app.app_context():
        inspector = inspect(db.engine)

        # products 테이블 존재 확인
        if "products" not in inspector.get_table_names():
            raise SystemExit("products 테이블이 존재하지 않습니다.")

        # 추가할 FK 컬럼 정의
        fk_columns = [
            {
                "column": "seller_id",
                "type": "INT",
                "ref_table": "product_sellers",
                "ref_column": "seller_id",
            },
            {
                "column": "mall_id",
                "type": "INT",
                "ref_table": "product_malls",
                "ref_column": "mall_id",
            },
            {
                "column": "brand_id",
                "type": "INT",
                "ref_table": "product_brands",
                "ref_column": "brand_id",
            },
        ]

        added = []
        skipped = []

        for fk in fk_columns:
            col_name = fk["column"]
            if column_exists(inspector, "products", col_name):
                skipped.append(col_name)
                continue

            # 컬럼 추가
            alter_sql = text(
                f"ALTER TABLE products ADD COLUMN {col_name} {fk['type']} NULL"
            )
            db.session.execute(alter_sql)
            print(f"✓ Added column: {col_name}")

            # FK 제약조건 추가
            fk_name = f"fk_products_{col_name}"
            fk_sql = text(
                f"ALTER TABLE products ADD CONSTRAINT {fk_name} "
                f"FOREIGN KEY ({col_name}) REFERENCES {fk['ref_table']}({fk['ref_column']})"
            )
            try:
                db.session.execute(fk_sql)
                print(f"✓ Added FK constraint: {fk_name}")
            except Exception as e:
                print(f"⚠ FK constraint {fk_name} skipped: {e}")

            added.append(col_name)

        db.session.commit()

        print("\n=== Migration Summary ===")
        print(f"  Added columns: {added if added else 'None'}")
        print(f"  Skipped (already exist): {skipped if skipped else 'None'}")

        # 검증
        inspector = inspect(db.engine)
        print("\n=== Verification ===")
        for fk in fk_columns:
            exists = column_exists(inspector, "products", fk["column"])
            status = "✓" if exists else "✗"
            print(f"  {status} {fk['column']}")

        print("\n✓ Migration complete.")


if __name__ == "__main__":
    run()
