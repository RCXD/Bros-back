import pytest
from app.extensions import db
from app.models.user import User, OauthType, AccountType
from werkzeug.security import generate_password_hash


@pytest.mark.no_cleanup
def test_generate_users(fixture_app):
    """더미 사용자 레코드를 데이터베이스에 생성"""
    n_users = 10
    n_admins = 2

    with fixture_app.app_context():
        # 일반 사용자 생성
        user_list = [
            User(
                username=f"user{i+1}",
                password_hash=generate_password_hash("1234"),
                email=f"user{i+1}@mail.com",
                address=f"Address for user {i+1}",
                oauth_type=OauthType.NONE,
                account_type=AccountType.USER,
                profile_img="static/default_profile.jpg",
            ) for i in range(n_users)
        ]

        # 관리자 사용자 생성
        admin_list = [
            User(
                username=f"admin{i+1}",
                password_hash=generate_password_hash("1234"),
                email=f"admin{i+1}@mail.com",
                address=f"Admin address {i+1}",
                oauth_type=OauthType.NONE,
                account_type=AccountType.ADMIN,
                profile_img="static/default_profile.jpg",
            ) for i in range(n_admins)
        ]

        # 데이터베이스에 모든 사용자 추가
        db.session.add_all(user_list + admin_list)
        db.session.commit()

        # 사용자가 생성되었는지 확인
        assert User.query.filter_by(account_type=AccountType.USER).count() == n_users
        assert User.query.filter_by(account_type=AccountType.ADMIN).count() == n_admins
        
        print(f"\n✓ {n_users}명 사용자와 {n_admins}명 관리자 생성 완료")
