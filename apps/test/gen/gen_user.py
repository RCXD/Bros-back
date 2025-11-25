import pytest
from apps.config.server import db
from apps.auth.models import User, OauthType, AccountType
from werkzeug.security import generate_password_hash

try:
    from logger import get_logger
except ImportError:
    from apps.common.logger import get_logger


@pytest.mark.no_cleanup
def test_generate_users(fixture_app):
    """더미 사용자 레코드를 데이터베이스에 생성"""

    log = get_logger()

    with fixture_app.app_context():
        # 앱 설정에서 생성할 사용자 수 가져오기
        n_users = fixture_app.config.get("NUM_USERS", 10)
        n_admins = fixture_app.config.get("NUM_ADMINS", 2)
        verbosity = fixture_app.config.get("VERBOSITY", 1)

        log.info(f"\n[1/5] 사용자 생성")
        log.debug(f"  목표: 일반 사용자 {n_users}명, 관리자 {n_admins}명")

        # 기존 사용자 확인 (중복 방지)
        existing_users = User.query.filter_by(account_type=AccountType.USER).count()
        existing_admins = User.query.filter_by(account_type=AccountType.ADMIN).count()

        if existing_users >= n_users and existing_admins >= n_admins:
            log.warning(
                f"  이미 {existing_users}명의 사용자와 {existing_admins}명의 관리자 존재, 건너뜀"
            )
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
            log.success(
                f"  {len(user_list)}명 사용자, {len(admin_list)}명 관리자 생성 완료"
            )

        # 최종 확인
        final_users = User.query.filter_by(account_type=AccountType.USER).count()
        final_admins = User.query.filter_by(account_type=AccountType.ADMIN).count()
        log.debug(f"  DB 총: {final_users}명 사용자, {final_admins}명 관리자")
