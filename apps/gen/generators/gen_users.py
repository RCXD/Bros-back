"""
사용자 데이터 생성기
"""
from pathlib import Path
import sys

# 프로젝트 루트를 경로에 추가
project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))

from app.extensions import db
from app.models.user import User, OauthType, AccountType
from werkzeug.security import generate_password_hash


def generate_users(app_context, num_users=10, num_admins=2):
    """
    사용자 계정 생성
    
    Args:
        app_context: Flask 앱 컨텍스트
        num_users: 생성할 일반 사용자 수
        num_admins: 생성할 관리자 수
        
    Returns:
        Tuple of (생성된 사용자 수, 생성된 관리자 수)
    """
    with app_context:
        existing_users = User.query.filter_by(account_type=AccountType.USER).count()
        existing_admins = User.query.filter_by(account_type=AccountType.ADMIN).count()
        
        if existing_users >= num_users and existing_admins >= num_admins:
            return 0, 0
        
        # 일반 사용자 생성
        user_list = []
        for i in range(1, num_users + 1):
            username = f"user{i}"
            if not User.query.filter_by(username=username).first():
                user_list.append(User(
                    username=username,
                    nickname=f"User{i}",
                    phone=f"010-0000-{str(i).zfill(4)}",
                    password_hash=generate_password_hash("1234"),
                    email=f"user{i}@mail.com",
                    address=f"Address for user {i}",
                    oauth_type=OauthType.NONE,
                    account_type=AccountType.USER,
                    profile_img="static/default_profile.jpg",
                ))
        
        # 관리자 사용자 생성
        admin_list = []
        for i in range(1, num_admins + 1):
            username = f"admin{i}"
            if not User.query.filter_by(username=username).first():
                admin_list.append(User(
                    username=username,
                    nickname=f"Admin{i}",
                    phone=f"010-0000-{str(i).zfill(4)}",
                    password_hash=generate_password_hash("1234"),
                    email=f"admin{i}@mail.com",
                    address=f"Admin address {i}",
                    oauth_type=OauthType.NONE,
                    account_type=AccountType.ADMIN,
                    profile_img="static/default_profile.jpg",
                ))
        
        if user_list or admin_list:
            db.session.add_all(user_list + admin_list)
            db.session.commit()
        
        return len(user_list), len(admin_list)


if __name__ == "__main__":
    from app import create_app
    from config import GeneratorConfig
    
    config = GeneratorConfig(use_test_env='--test' in sys.argv)
    config.print_config()
    
    app = create_app()
    
    with app.app_context():
        users, admins = generate_users(
            app.app_context(),
            num_users=config.num_users,
            num_admins=config.num_admins
        )
        print(f"\n생성됨: 사용자 {users}명, 관리자 {admins}명")
