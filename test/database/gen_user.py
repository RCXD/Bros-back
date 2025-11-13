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
        # 기존 사용자 확인 (중복 방지)
        existing_users = User.query.filter_by(account_type=AccountType.USER).count()
        existing_admins = User.query.filter_by(account_type=AccountType.ADMIN).count()
        
        if existing_users >= n_users and existing_admins >= n_admins:
            print(f"\n⚠ 이미 {existing_users}명의 사용자와 {existing_admins}명의 관리자가 존재합니다. 건너뜁니다.")
            return
        
        # 일반 사용자 생성
        user_list = []
        for i in range(n_users):
            username = f"user{i+1}"
            # 이미 존재하는 사용자는 건너뛰기
            if not User.query.filter_by(username=username).first():
                user_list.append(
                    User(
                        username=username,
                        nickname=f"User{i+1}",
                        phone=f"010-0000-{str(i+1).zfill(4)}",
                        password_hash=generate_password_hash("1234"),
                        email=f"user{i+1}@mail.com",
                        address=f"Address for user {i+1}",
                        oauth_type=OauthType.NONE,
                        account_type=AccountType.USER,
                        profile_img="static/default_profile.jpg",
                    )
                )

        # 관리자 사용자 생성
        admin_list = []
        for i in range(n_admins):
            username = f"admin{i+1}"
            # 이미 존재하는 관리자는 건너뛰기
            if not User.query.filter_by(username=username).first():
                admin_list.append(
                    User(
                        username=username,
                        nickname=f"Admin{i+1}",
                        phone=f"010-0000-{str(i+1).zfill(4)}",
                        password_hash=generate_password_hash("1234"),
                        email=f"admin{i+1}@mail.com",
                        address=f"Admin address {i+1}",
                        oauth_type=OauthType.NONE,
                        account_type=AccountType.ADMIN,
                        profile_img="static/default_profile.jpg",
                    )
                )

        # 데이터베이스에 모든 사용자 추가
        if user_list or admin_list:
            db.session.add_all(user_list + admin_list)
            db.session.commit()
            print(f"\n✓ {len(user_list)}명 사용자와 {len(admin_list)}명 관리자 생성 완료")
        
        # 최종 확인
        final_users = User.query.filter_by(account_type=AccountType.USER).count()
        final_admins = User.query.filter_by(account_type=AccountType.ADMIN).count()
        print(f"  데이터베이스의 총 사용자: {final_users}명, 관리자: {final_admins}명")
