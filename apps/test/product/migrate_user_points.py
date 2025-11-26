"""
users 테이블에 points 컬럼 추가 마이그레이션

Usage:
    python apps/test/product/migrate_user_points.py
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

        # users 테이블 존재 확인
        if "users" not in inspector.get_table_names():
            raise SystemExit("users 테이블이 존재하지 않습니다.")

        # points 컬럼 확인
        if column_exists(inspector, "users", "points"):
            print("✓ points 컬럼이 이미 존재합니다.")
        else:
            # 컬럼 추가
            alter_sql = text(
                "ALTER TABLE users ADD COLUMN points INT NOT NULL DEFAULT 0"
            )
            db.session.execute(alter_sql)
            db.session.commit()
            print("✓ points 컬럼이 추가되었습니다.")

        # 검증
        inspector = inspect(db.engine)
        exists = column_exists(inspector, "users", "points")
        status = "✓" if exists else "✗"
        print(f"\n=== Verification ===")
        print(f"  {status} users.points")

        # 현재 포인트 통계
        result = db.session.execute(
            text(
                "SELECT COUNT(*) as total, SUM(points) as sum_points, AVG(points) as avg_points FROM users"
            )
        )
        row = result.fetchone()
        print(f"\n=== Points Statistics ===")
        print(f"  Total users: {row[0]}")
        print(f"  Sum points: {row[1] or 0}")
        print(f"  Avg points: {row[2] or 0:.2f}")

        print("\n✓ Migration complete.")


if __name__ == "__main__":
    run()
