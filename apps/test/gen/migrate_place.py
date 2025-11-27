"""
Place 모델 마이그레이션 스크립트
PlaceCategory, PlaceType 테이블 생성 및 Place 테이블에 새 필드 추가
+ Google/Kakao 외부 API 데이터 필드 추가
"""

import os
import sys

# 프로젝트 루트 추가
sys.path.insert(
    0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(__file__))))
)

from sqlalchemy import text


def add_column_safe(db, column_sql, column_name):
    """안전하게 컬럼 추가 (이미 존재하면 스킵)"""
    try:
        db.session.execute(text(f"ALTER TABLE place ADD COLUMN {column_sql}"))
        print(f"     - {column_name} 추가 완료")
        return True
    except Exception as e:
        if "Duplicate column" in str(e):
            print(f"     - {column_name} 이미 존재")
        else:
            print(f"     - {column_name} 추가 실패: {e}")
        return False


def add_index_safe(db, index_sql, index_name):
    """안전하게 인덱스 추가 (이미 존재하면 스킵)"""
    try:
        db.session.execute(text(index_sql))
        print(f"     - {index_name} 추가 완료")
        return True
    except Exception as e:
        if "Duplicate" in str(e):
            print(f"     - {index_name} 이미 존재")
        else:
            print(f"     - {index_name} 추가 실패: {e}")
        return False


def migrate_place_tables():
    """Place 관련 테이블 마이그레이션"""
    from apps.app import create_app
    from apps.config.server import db

    app = create_app()

    with app.app_context():
        print("\n[Place Migration] 테이블 마이그레이션 시작...")

        # PlaceCategory 테이블 생성
        print("  1. PlaceCategory 테이블 생성...")
        db.session.execute(
            text(
                """
            CREATE TABLE IF NOT EXISTS place_category (
                category_id INT AUTO_INCREMENT PRIMARY KEY,
                name VARCHAR(50) NOT NULL UNIQUE,
                description VARCHAR(255)
            ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
        """
            )
        )

        # PlaceType 테이블 생성
        print("  2. PlaceType 테이블 생성...")
        db.session.execute(
            text(
                """
            CREATE TABLE IF NOT EXISTS place_type (
                type_id INT AUTO_INCREMENT PRIMARY KEY,
                name VARCHAR(50) NOT NULL UNIQUE,
                display_name VARCHAR(100),
                category_id INT,
                icon VARCHAR(50),
                FOREIGN KEY (category_id) REFERENCES place_category(category_id) ON DELETE SET NULL
            ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
        """
            )
        )

        # Place 테이블에 새 컬럼 추가
        print("  3. Place 테이블에 기본 컬럼 추가...")

        # category_id 컬럼
        try:
            db.session.execute(
                text(
                    """
                ALTER TABLE place ADD COLUMN category_id INT,
                ADD CONSTRAINT fk_place_category FOREIGN KEY (category_id) 
                REFERENCES place_category(category_id) ON DELETE SET NULL
            """
                )
            )
            print("     - category_id 추가 완료")
        except Exception as e:
            if "Duplicate column" in str(e):
                print("     - category_id 이미 존재")
            else:
                print(f"     - category_id 추가 실패: {e}")

        # type_id 컬럼
        try:
            db.session.execute(
                text(
                    """
                ALTER TABLE place ADD COLUMN type_id INT,
                ADD CONSTRAINT fk_place_type FOREIGN KEY (type_id) 
                REFERENCES place_type(type_id) ON DELETE SET NULL
            """
                )
            )
            print("     - type_id 추가 완료")
        except Exception as e:
            if "Duplicate column" in str(e):
                print("     - type_id 이미 존재")
            else:
                print(f"     - type_id 추가 실패: {e}")

        # post_id 컬럼
        try:
            db.session.execute(
                text(
                    """
                ALTER TABLE place ADD COLUMN post_id INT,
                ADD CONSTRAINT fk_place_post FOREIGN KEY (post_id) 
                REFERENCES posts(post_id) ON DELETE SET NULL
            """
                )
            )
            print("     - post_id 추가 완료")
        except Exception as e:
            if "Duplicate column" in str(e):
                print("     - post_id 이미 존재")
            else:
                print(f"     - post_id 추가 실패: {e}")

        # 기본 필드들
        add_column_safe(
            db, "recommendation_score DECIMAL(2,1) DEFAULT 3.0", "recommendation_score"
        )
        add_column_safe(db, "danger_level DECIMAL(3,1) DEFAULT 0.0", "danger_level")
        add_column_safe(
            db, "geometry_type VARCHAR(20) DEFAULT 'point'", "geometry_type"
        )

        # ========== Google Places API 필드 ==========
        print("\n  4. Google Places API 필드 추가...")
        add_column_safe(db, "google_place_id VARCHAR(255) UNIQUE", "google_place_id")
        add_column_safe(db, "google_name VARCHAR(255)", "google_name")
        add_column_safe(db, "google_address VARCHAR(500)", "google_address")
        add_column_safe(db, "google_rating DECIMAL(2,1)", "google_rating")
        add_column_safe(
            db, "google_reviews_count INT DEFAULT 0", "google_reviews_count"
        )
        add_column_safe(db, "google_price_level INT", "google_price_level")
        add_column_safe(db, "google_phone VARCHAR(50)", "google_phone")
        add_column_safe(db, "google_website VARCHAR(500)", "google_website")
        add_column_safe(db, "google_opening_hours JSON", "google_opening_hours")
        add_column_safe(db, "google_photos JSON", "google_photos")
        add_column_safe(db, "google_types JSON", "google_types")
        add_column_safe(
            db, "google_business_status VARCHAR(50)", "google_business_status"
        )
        add_column_safe(db, "google_last_synced DATETIME", "google_last_synced")

        # ========== Kakao Local API 필드 ==========
        print("\n  5. Kakao Local API 필드 추가...")
        add_column_safe(db, "kakao_place_id VARCHAR(255) UNIQUE", "kakao_place_id")
        add_column_safe(db, "kakao_name VARCHAR(255)", "kakao_name")
        add_column_safe(db, "kakao_address VARCHAR(500)", "kakao_address")
        add_column_safe(db, "kakao_road_address VARCHAR(500)", "kakao_road_address")
        add_column_safe(db, "kakao_phone VARCHAR(50)", "kakao_phone")
        add_column_safe(db, "kakao_category_name VARCHAR(255)", "kakao_category_name")
        add_column_safe(
            db, "kakao_category_group_code VARCHAR(20)", "kakao_category_group_code"
        )
        add_column_safe(
            db, "kakao_category_group_name VARCHAR(50)", "kakao_category_group_name"
        )
        add_column_safe(db, "kakao_url VARCHAR(500)", "kakao_url")
        add_column_safe(db, "kakao_last_synced DATETIME", "kakao_last_synced")

        # ========== 통합 정보 필드 ==========
        print("\n  6. 통합 정보 필드 추가...")
        add_column_safe(db, "verified BOOLEAN DEFAULT FALSE", "verified")
        add_column_safe(db, "data_source VARCHAR(50)", "data_source")

        # 인덱스 추가
        print("\n  7. 인덱스 추가...")
        add_index_safe(
            db,
            "CREATE INDEX idx_place_category ON place(category_id)",
            "idx_place_category",
        )
        add_index_safe(
            db, "CREATE INDEX idx_place_type ON place(type_id)", "idx_place_type"
        )
        add_index_safe(
            db, "CREATE INDEX idx_place_post ON place(post_id)", "idx_place_post"
        )
        add_index_safe(
            db,
            "CREATE INDEX idx_place_google_id ON place(google_place_id)",
            "idx_place_google_id",
        )
        add_index_safe(
            db,
            "CREATE INDEX idx_place_kakao_id ON place(kakao_place_id)",
            "idx_place_kakao_id",
        )
        add_index_safe(
            db,
            "CREATE INDEX idx_place_verified ON place(verified)",
            "idx_place_verified",
        )
        add_index_safe(
            db,
            "CREATE INDEX idx_place_data_source ON place(data_source)",
            "idx_place_data_source",
        )

        db.session.commit()
        print("\n  ✅ Place 마이그레이션 완료!")


if __name__ == "__main__":
    migrate_place_tables()
