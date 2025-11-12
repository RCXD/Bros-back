"""
테스트 데이터베이스에서 생성된 사용자 확인
"""
import pytest
from app.extensions import db
from app.models.user import User, AccountType


@pytest.mark.no_cleanup
def test_verify_users_exist(fixture_app):
    """데이터베이스에 사용자가 존재하는지 확인"""
    with fixture_app.app_context():
        users = User.query.filter_by(account_type=AccountType.USER).all()
        admins = User.query.filter_by(account_type=AccountType.ADMIN).all()
        
        print(f"\n--- 데이터베이스 내용 ---")
        print(f"총 사용자: {len(users)}")
        print(f"총 관리자: {len(admins)}")
        
        if users:
            print("\n사용자 계정:")
            for user in users:
                print(f"  - {user.username} ({user.email})")
        
        if admins:
            print("\n관리자 계정:")
            for admin in admins:
                print(f"  - {admin.username} ({admin.email})")
