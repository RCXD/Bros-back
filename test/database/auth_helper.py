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
    
    data = {
        'username': username,
        'password': password
    }
    
    for attempt in range(max_retries):
        try:
            response = requests.post(url, json=data, timeout=timeout)
            
            if response.status_code == 200:
                result = response.json()
                return result.get('access_token')
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


def get_all_user_tokens(base_url, num_users=10):
    """
    여러 사용자의 토큰을 미리 획득
    
    Args:
        base_url: API 서버 주소
        num_users: 사용자 수 (기본값: 10)
        
    Returns:
        dict: {user_email: token} 매핑 (email을 key로 사용하여 기존 코드와 호환성 유지)
    """
    tokens = {}
    
    print(f"\n🔐 사용자 토큰 획득 중...")
    
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
