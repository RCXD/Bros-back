"""
JWT 토큰 관리를 위한 인증 헬퍼
"""
import requests
import time


def get_user_token(base_url, username, password="1234", timeout=30, max_retries=3):
    """
    사용자 로그인을 통해 JWT 토큰 획득
    
    Args:
        base_url: API 서버 URL
        username: 사용자 아이디
        password: 사용자 비밀번호 (기본값: 1234)
        timeout: 요청 타임아웃 초 단위 (기본값: 30)
        max_retries: 최대 재시도 횟수 (기본값: 3)
        
    Returns:
        str: JWT access token 또는 None
    """
    url = f"{base_url.rstrip('/')}/auth/login"
    data = {'username': username, 'password': password}
    
    for attempt in range(max_retries):
        try:
            response = requests.post(url, json=data, timeout=timeout)
            
            if response.status_code == 200:
                return response.json().get('access_token')
            
            if attempt < max_retries - 1:
                time.sleep(2)
                continue
            return None
            
        except requests.exceptions.Timeout:
            if attempt < max_retries - 1:
                time.sleep(3)
                continue
            return None
            
        except Exception:
            if attempt < max_retries - 1:
                time.sleep(2)
                continue
            return None
    
    return None


def get_all_user_tokens(base_url, num_users=10):
    """
    여러 사용자의 토큰을 일괄 획득
    
    Args:
        base_url: API 서버 URL
        num_users: 사용자 수 (기본값: 10)
        
    Returns:
        dict: {user_email: token} 매핑
    """
    tokens = {}
    
    for i in range(1, num_users + 1):
        username = f"user{i}"
        email = f"user{i}@mail.com"
        token = get_user_token(base_url, username)
        
        if token:
            tokens[email] = token
    
    return tokens
