"""
Notification과 Mention 테이블에 item_type/item_id 패턴을 직접 적용하는 스크립트
"""

import pymysql

conn = pymysql.connect(
    host="192.168.1.79", user="user1", password="1234", database="404found_test2"
)

cursor = conn.cursor()

try:
    print("=== Notification 테이블 업그레이드 시작 ===\n")

    # 1. Notification 테이블에 새 enum 타입과 컬럼 추가
    print("1. UNFOLLOW을 NotificationType enum에 추가...")
    cursor.execute(
        """
        ALTER TABLE notifications 
        MODIFY COLUMN type ENUM(
            'MENTION','POST_LIKE','REPLY_LIKE','COMMENT','FOLLOW',
            'FRIEND_REQUEST','REPLY','REPLY_TO_REPLY','PRODUCT_RECOMMENDATION','UNFOLLOW'
        ) NOT NULL
    """
    )

    print("2. NotificationItemType enum과 item_type 컬럼 추가...")
    cursor.execute(
        """
        ALTER TABLE notifications
        ADD COLUMN item_type ENUM('POST', 'REPLY', 'MENTION', 'PRODUCT', 'FOLLOW', 'USER') NULL AFTER to_user_id,
        ADD COLUMN item_id INT NULL AFTER item_type,
        ADD COLUMN follow_id INT NULL AFTER item_id
    """
    )

    print("3. 기존 데이터 마이그레이션...")

    # post_id -> item_type=POST, item_id=post_id
    cursor.execute(
        """
        UPDATE notifications
        SET item_type = 'POST', item_id = post_id
        WHERE post_id IS NOT NULL
    """
    )
    print(f"   - POST: {cursor.rowcount} rows")

    # reply_id -> item_type=REPLY, item_id=reply_id
    cursor.execute(
        """
        UPDATE notifications
        SET item_type = 'REPLY', item_id = reply_id
        WHERE reply_id IS NOT NULL AND item_type IS NULL
    """
    )
    print(f"   - REPLY: {cursor.rowcount} rows")

    # mention_id -> item_type=MENTION, item_id=mention_id
    cursor.execute(
        """
        UPDATE notifications
        SET item_type = 'MENTION', item_id = mention_id
        WHERE mention_id IS NOT NULL AND item_type IS NULL
    """
    )
    print(f"   - MENTION: {cursor.rowcount} rows")

    # product_id -> item_type=PRODUCT, item_id=product_id
    cursor.execute(
        """
        UPDATE notifications
        SET item_type = 'PRODUCT', item_id = product_id
        WHERE product_id IS NOT NULL AND item_type IS NULL
    """
    )
    print(f"   - PRODUCT: {cursor.rowcount} rows")

    # FRIEND_REQUEST와 기타 -> item_type=USER, item_id=from_user_id
    cursor.execute(
        """
        UPDATE notifications
        SET item_type = 'USER', item_id = from_user_id
        WHERE item_type IS NULL
    """
    )
    print(f"   - USER: {cursor.rowcount} rows")

    print("4. 외래키 제약조건 제거...")
    # 외래키 이름 확인
    cursor.execute(
        """
        SELECT CONSTRAINT_NAME
        FROM information_schema.KEY_COLUMN_USAGE
        WHERE TABLE_SCHEMA = '404found_test2'
        AND TABLE_NAME = 'notifications'
        AND CONSTRAINT_NAME != 'PRIMARY'
        AND REFERENCED_TABLE_NAME IS NOT NULL
    """
    )
    fks = cursor.fetchall()
    for (fk_name,) in fks:
        try:
            cursor.execute(f"ALTER TABLE notifications DROP FOREIGN KEY {fk_name}")
            print(f"   - Dropped FK: {fk_name}")
        except Exception as e:
            print(f"   - Could not drop FK {fk_name}: {e}")

    print("5. 옛날 컬럼 제거...")
    cursor.execute(
        """
        ALTER TABLE notifications
        DROP COLUMN post_id,
        DROP COLUMN reply_id,
        DROP COLUMN mention_id,
        DROP COLUMN product_id
    """
    )

    print("6. 인덱스 추가...")
    cursor.execute(
        """
        CREATE INDEX idx_notification_receiver ON notifications(to_user_id, is_checked, created_at)
    """
    )
    cursor.execute(
        """
        CREATE INDEX idx_notification_item ON notifications(item_type, item_id)
    """
    )

    print("\n=== Mention 테이블 업그레이드 시작 ===\n")

    print("1. MentionItemType enum과 item_type, item_id 컬럼 추가...")
    cursor.execute(
        """
        ALTER TABLE mentions
        ADD COLUMN item_type ENUM('POST', 'REPLY') NOT NULL DEFAULT 'POST' AFTER mentioned_user_id,
        ADD COLUMN item_id INT NOT NULL DEFAULT 0 AFTER item_type
    """
    )

    print("2. 기존 데이터 마이그레이션...")

    # post_id -> item_type=POST, item_id=post_id
    cursor.execute(
        """
        UPDATE mentions
        SET item_type = 'POST', item_id = post_id
        WHERE post_id IS NOT NULL
    """
    )
    print(f"   - POST: {cursor.rowcount} rows")

    # reply_id -> item_type=REPLY, item_id=reply_id
    cursor.execute(
        """
        UPDATE mentions
        SET item_type = 'REPLY', item_id = reply_id
        WHERE reply_id IS NOT NULL AND item_id = 0
    """
    )
    print(f"   - REPLY: {cursor.rowcount} rows")

    print("3. CHECK 제약조건 제거...")
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

    print("4. 외래키 제약조건 제거...")
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

    print("5. 옛날 컬럼 제거...")
    cursor.execute(
        """
        ALTER TABLE mentions
        DROP COLUMN post_id,
        DROP COLUMN reply_id
    """
    )

    print("6. 인덱스와 제약조건 추가...")
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

    cursor.execute(
        """
        ALTER TABLE mentions
        ADD UNIQUE KEY unique_mention (mentioner_id, mentioned_user_id, item_type, item_id)
    """
    )
    cursor.execute(
        """
        CREATE INDEX idx_mention_user ON mentions(mentioned_user_id, is_checked)
    """
    )
    cursor.execute(
        """
        CREATE INDEX idx_mention_item ON mentions(item_type, item_id)
    """
    )

    print("6. DEFAULT 제거...")
    cursor.execute(
        """
        ALTER TABLE mentions
        ALTER COLUMN item_type DROP DEFAULT,
        ALTER COLUMN item_id DROP DEFAULT
    """
    )

    conn.commit()
    print("\n=== 모든 마이그레이션 완료! ===")

    # 결과 확인
    print("\n=== Notification 테이블 구조 ===")
    cursor.execute("DESCRIBE notifications")
    for col in cursor.fetchall():
        print(f"  {col[0]:25} {col[1]}")

    print("\n=== Mention 테이블 구조 ===")
    cursor.execute("DESCRIBE mentions")
    for col in cursor.fetchall():
        print(f"  {col[0]:25} {col[1]}")

    # alembic_version 업데이트
    cursor.execute(
        "UPDATE alembic_version SET version_num='notification_mention_itemtype'"
    )
    conn.commit()
    print("\n=== alembic_version 업데이트 완료 ===")

except Exception as e:
    conn.rollback()
    print(f"\n❌ 에러 발생: {e}")
    import traceback

    traceback.print_exc()
finally:
    cursor.close()
    conn.close()
