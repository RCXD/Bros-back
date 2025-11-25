"""
Mention 테이블 migration 완료 스크립트
"""

import pymysql

conn = pymysql.connect(
    host="192.168.1.79", user="user1", password="1234", database="404found_test2"
)

cursor = conn.cursor()

try:
    print("=== Mention 테이블 업그레이드 계속 ===\n")

    print("1. 기존 데이터 마이그레이션 (재실행)...")

    # post_id -> item_type=POST, item_id=post_id
    cursor.execute(
        """
        UPDATE mentions
        SET item_type = 'POST', item_id = post_id
        WHERE post_id IS NOT NULL AND (item_id IS NULL OR item_id = 0)
    """
    )
    print(f"   - POST: {cursor.rowcount} rows")

    # reply_id -> item_type=REPLY, item_id=reply_id
    cursor.execute(
        """
        UPDATE mentions
        SET item_type = 'REPLY', item_id = reply_id
        WHERE reply_id IS NOT NULL AND (item_id IS NULL OR item_id = 0)
    """
    )
    print(f"   - REPLY: {cursor.rowcount} rows")

    print("2. CHECK 제약조건 제거...")
    cursor.execute(
        """
        SELECT CONSTRAINT_NAME
        FROM information_schema.TABLE_CONSTRAINTS
        WHERE TABLE_SCHEMA = '404found_test2'
        AND TABLE_NAME = 'mentions'
        AND CONSTRAINT_TYPE = 'CHECK'
    """
    )
    checks = cursor.fetchall()
    for (check_name,) in checks:
        try:
            cursor.execute(f"ALTER TABLE mentions DROP CHECK {check_name}")
            print(f"   - Dropped CHECK: {check_name}")
        except Exception as e:
            print(f"   - Could not drop CHECK {check_name}: {e}")

    print("3. 외래키 제약조건 제거...")
    cursor.execute(
        """
        SELECT CONSTRAINT_NAME
        FROM information_schema.KEY_COLUMN_USAGE
        WHERE TABLE_SCHEMA = '404found_test2'
        AND TABLE_NAME = 'mentions'
        AND CONSTRAINT_NAME != 'PRIMARY'
        AND REFERENCED_TABLE_NAME IS NOT NULL
    """
    )
    fks = cursor.fetchall()
    for (fk_name,) in fks:
        try:
            cursor.execute(f"ALTER TABLE mentions DROP FOREIGN KEY {fk_name}")
            print(f"   - Dropped FK: {fk_name}")
        except Exception as e:
            print(f"   - Could not drop FK {fk_name}: {e}")

    print("4. 옛날 컬럼 제거...")
    cursor.execute(
        """
        ALTER TABLE mentions
        DROP COLUMN post_id,
        DROP COLUMN reply_id
    """
    )

    print("5. 인덱스와 제약조건 추가...")
    # 기존 unique constraint 제거
    cursor.execute(
        """
        SELECT CONSTRAINT_NAME
        FROM information_schema.TABLE_CONSTRAINTS
        WHERE TABLE_SCHEMA = '404found_test2'
        AND TABLE_NAME = 'mentions'
        AND CONSTRAINT_TYPE = 'UNIQUE'
    """
    )
    unique_constraints = cursor.fetchall()
    for (uc_name,) in unique_constraints:
        try:
            cursor.execute(f"ALTER TABLE mentions DROP INDEX {uc_name}")
            print(f"   - Dropped unique constraint: {uc_name}")
        except Exception as e:
            print(f"   - Could not drop unique constraint {uc_name}: {e}")

    # 새 unique constraint 추가
    try:
        cursor.execute(
            """
            ALTER TABLE mentions
            ADD UNIQUE KEY unique_mention (mentioner_id, mentioned_user_id, item_type, item_id)
        """
        )
        print("   - Added unique_mention constraint")
    except Exception as e:
        print(f"   - Could not add unique constraint: {e}")

    # 인덱스 추가
    try:
        cursor.execute(
            """
            CREATE INDEX idx_mention_user ON mentions(mentioned_user_id, is_checked)
        """
        )
        print("   - Added idx_mention_user")
    except Exception as e:
        print(f"   - Could not add idx_mention_user: {e}")

    try:
        cursor.execute(
            """
            CREATE INDEX idx_mention_item ON mentions(item_type, item_id)
        """
        )
        print("   - Added idx_mention_item")
    except Exception as e:
        print(f"   - Could not add idx_mention_item: {e}")

    conn.commit()
    print("\n=== Mention 테이블 마이그레이션 완료! ===")

    # 결과 확인
    print("\n=== Mention 테이블 최종 구조 ===")
    cursor.execute("DESCRIBE mentions")
    for col in cursor.fetchall():
        print(f"  {col[0]:25} {col[1]}")

    # alembic_version 업데이트
    cursor.execute(
        "UPDATE alembic_version SET version_num='notification_mention_itemtype'"
    )
    conn.commit()
    print("\n=== alembic_version 업데이트 완료 ===")

    # message 필드 확인
    print("\n=== Notification message 필드 확인 ===")
    cursor.execute("DESCRIBE notifications")
    cols = [col[0] for col in cursor.fetchall()]
    if "message" in cols:
        print("✓ message 필드 존재")
    else:
        print("✗ message 필드 없음 - 추가 필요")
        cursor.execute(
            "ALTER TABLE notifications ADD COLUMN message VARCHAR(255) AFTER item_id"
        )
        conn.commit()
        print("✓ message 필드 추가 완료")

except Exception as e:
    conn.rollback()
    print(f"\n❌ 에러 발생: {e}")
    import traceback

    traceback.print_exc()
finally:
    cursor.close()
    conn.close()
