"""
Post-Place 연동 마이그레이션 스크립트
Post 테이블에 place_id 컬럼 추가
"""

import os
import sys

# 프로젝트 루트 추가
sys.path.insert(
    0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(__file__))))
)

from sqlalchemy import text


def migrate_post_place():
    """Post 테이블에 place_id 컬럼 추가"""
    from apps.app import create_app
    from apps.config.server import db

    app = create_app()

    with app.app_context():
        print("\n[Post-Place Migration] 마이그레이션 시작...")

        # place_id 컬럼 추가
        print("  1. posts 테이블에 place_id 컬럼 추가...")
        try:
            db.session.execute(
                text(
                    """
                ALTER TABLE posts 
                ADD COLUMN place_id INT NULL,
                ADD CONSTRAINT fk_posts_place 
                FOREIGN KEY (place_id) REFERENCES place(place_id) ON DELETE SET NULL
            """
                )
            )
            print("     - place_id 컬럼 추가 완료")
        except Exception as e:
            if "Duplicate column" in str(e):
                print("     - place_id 컬럼 이미 존재")
            else:
                print(f"     - place_id 추가 실패: {e}")

        # 인덱스 추가
        print("  2. 인덱스 추가...")
        try:
            db.session.execute(text("CREATE INDEX idx_posts_place ON posts(place_id)"))
            print("     - idx_posts_place 추가 완료")
        except Exception as e:
            if "Duplicate" in str(e):
                print("     - idx_posts_place 이미 존재")
            else:
                print(f"     - idx_posts_place 추가 실패: {e}")

        db.session.commit()
        print("\n  ✅ Post-Place 마이그레이션 완료!")

        # 검증
        print("\n  3. 검증 중...")

        # 컬럼 존재 확인
        result = db.session.execute(text("SHOW COLUMNS FROM posts LIKE 'place_id'"))
        columns = result.fetchall()
        if columns:
            print("     ✅ place_id 컬럼 존재 확인")
        else:
            print("     ❌ place_id 컬럼이 없습니다!")
            return

        # FK 확인
        result = db.session.execute(
            text(
                """
                SELECT CONSTRAINT_NAME 
                FROM information_schema.TABLE_CONSTRAINTS 
                WHERE TABLE_NAME = 'posts' 
                AND CONSTRAINT_TYPE = 'FOREIGN KEY'
                AND CONSTRAINT_NAME = 'fk_posts_place'
            """
            )
        )
        fks = result.fetchall()
        if fks:
            print("     ✅ Foreign Key 제약조건 확인")
        else:
            print(
                "     ⚠️ Foreign Key 제약조건이 없습니다 (이미 다른 이름으로 존재할 수 있음)"
            )

        # 인덱스 확인
        result = db.session.execute(
            text("SHOW INDEX FROM posts WHERE Key_name = 'idx_posts_place'")
        )
        indexes = result.fetchall()
        if indexes:
            print("     ✅ 인덱스 확인")
        else:
            print("     ⚠️ 인덱스가 없습니다")

        # 테스트 쿼리 실행
        print("\n  4. 테스트 쿼리 실행...")

        # Post와 Place 조인 테스트
        result = db.session.execute(
            text(
                """
                SELECT p.post_id, p.content, pl.name as place_name
                FROM posts p
                LEFT JOIN place pl ON p.place_id = pl.place_id
                LIMIT 5
            """
            )
        )
        rows = result.fetchall()
        print(f"     ✅ JOIN 쿼리 성공 (결과: {len(rows)}개 행)")

        # Place에서 연결된 Post 조회 테스트
        result = db.session.execute(
            text(
                """
                SELECT pl.place_id, pl.name, COUNT(p.post_id) as post_count
                FROM place pl
                LEFT JOIN posts p ON pl.place_id = p.place_id
                GROUP BY pl.place_id, pl.name
                LIMIT 5
            """
            )
        )
        rows = result.fetchall()
        print(f"     ✅ 역방향 JOIN 쿼리 성공 (결과: {len(rows)}개 행)")

        print("\n  ✅ 모든 검증 완료!")


if __name__ == "__main__":
    migrate_post_place()
