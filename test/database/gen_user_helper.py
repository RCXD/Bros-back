"""
JWT 토큰 생성 헬퍼
"""

import requests
import time


def get_user_token(base_url, username, password="1234", timeout=30, max_retries=3):
    """
    사용자 로그인을 통해 JWT 토큰 획득

    Args:
        base_url: API 서버 주소
        username: 사용자 아이디 (username)
        password: 비밀번호 (기본값: 1234)
        timeout: 요청 타임아웃 (초, 기본값: 30)
        max_retries: 최대 재시도 횟수 (기본값: 3)

    Returns:
        str: JWT access token 또는 None
    """
    url = f"{base_url.rstrip('/')}/auth/login"

    data = {"username": username, "password": password}

    for attempt in range(max_retries):
        try:
            response = requests.post(url, json=data, timeout=timeout)

            if response.status_code == 200:
                result = response.json()
                return result.get("access_token")
            else:
                print(f"❌ 로그인 실패 ({username}): {response.status_code}")
                print(f"   응답: {response.text}")
                if attempt < max_retries - 1:
                    print(f"   재시도 {attempt + 1}/{max_retries}...")
                    time.sleep(2)
                    continue
                return None
        except requests.exceptions.Timeout:
            print(f"⏱️ 로그인 타임아웃 ({username}) - 시도 {attempt + 1}/{max_retries}")
            if attempt < max_retries - 1:
                time.sleep(3)
                continue
            return None
        except Exception as e:
            print(f"❌ 로그인 예외 ({username}, 시도 {attempt + 1}/{max_retries}): {e}")
            if attempt < max_retries - 1:
                time.sleep(2)
                continue
            return None

    return None


def get_all_user_tokens_from_db(
    app, base_url, expected_users=None, expected_admins=None
):
    """
    데이터베이스에서 실제 사용자 수를 확인하고 토큰을 획득

    Args:
        app: Flask 앱 인스턴스 (DB 조회용)
        base_url: API 서버 주소
        expected_users: 예상되는 일반 사용자 수 (경고용, 선택)
        expected_admins: 예상되는 관리자 수 (경고용, 선택)

    Returns:
        dict: {user_email: token} 매핑
    """
    from app_legacy.models.user import User, AccountType

    with app.app_context():
        # 실제 사용자 수 확인
        total_users = User.query.count()
        num_regular_users = User.query.filter_by(account_type=AccountType.USER).count()
        num_admins = User.query.filter_by(account_type=AccountType.ADMIN).count()

        print(f"\n📊 데이터베이스 사용자 현황:")
        print(f"  일반 사용자: {num_regular_users}명")
        print(f"  관리자: {num_admins}명")
        print(f"  총: {total_users}명")

        # 예상 수와 비교하여 경고
        if expected_users is not None and num_regular_users != expected_users:
            print(
                f"  ⚠️  경고: 예상 일반 사용자({expected_users}명)와 실제({num_regular_users}명)가 다릅니다!"
            )
        if expected_admins is not None and num_admins != expected_admins:
            print(
                f"  ⚠️  경고: 예상 관리자({expected_admins}명)와 실제({num_admins}명)가 다릅니다!"
            )

        # 모든 사용자 가져오기
        all_users = User.query.all()

    tokens = {}

    print(f"\n🔐 {total_users}명의 사용자 토큰 획득 중...")

    for user in all_users:
        token = get_user_token(base_url, user.username)

        if token:
            tokens[user.email] = token
            user_type = "👑" if user.account_type == AccountType.ADMIN else "👤"
            print(f"  ✓ {user_type} {user.username} ({user.email})")
        else:
            print(f"  ✗ {user.username} (실패)")

    print(f"  총 {len(tokens)}/{total_users}개 토큰 획득\n")

    return tokens


def get_all_user_tokens(base_url, num_users=10):
    """
    여러 사용자의 토큰을 미리 획득 (레거시 함수, 하위 호환성 유지)

    Args:
        base_url: API 서버 주소
        num_users: 사용자 수 (기본값: 10)

    Returns:
        dict: {user_email: token} 매핑 (email을 key로 사용하여 기존 코드와 호환성 유지)
    """
    tokens = {}

    print(f"\n🔐 {num_users}명의 사용자 토큰 획득 중...")

    for i in range(1, num_users + 1):
        username = f"user{i}"
        email = f"user{i}@mail.com"
        token = get_user_token(base_url, username)

        if token:
            # email을 key로 사용 (User 모델의 email 필드와 매칭하기 위해)
            tokens[email] = token
            print(f"  ✓ {username} ({email})")
        else:
            print(f"  ✗ {username} (실패)")

    print(f"  총 {len(tokens)}/{num_users}개 토큰 획득\n")

    return tokens
