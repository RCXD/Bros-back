"""
API 엔드포인트 헬퍼
.endpoint.env 파일에서 엔드포인트를 로드하여 사용
"""

import os
from pathlib import Path
from dotenv import load_dotenv


class APIEndpoints:
    """API 엔드포인트 관리 클래스"""

    def __init__(self, api_version="v1"):
        """
        Args:
            api_version: 'v1' 또는 'legacy'
        """
        # .endpoint.env 파일 로드 (프로젝트 루트에서)
        endpoint_env = Path(__file__).parent.parent.parent / ".endpoint.env"
        if endpoint_env.exists():
            load_dotenv(dotenv_path=endpoint_env)
            # print(f"[OK] Loaded endpoints from: {endpoint_env}")
        # else:
        #     print(f"[WARN] Endpoint file not found: {endpoint_env}")

        self.api_version = api_version.lower()
        self._prefix = "V1_" if self.api_version == "v1" else "LEGACY_"

    def _get_endpoint(self, key):
        """환경 변수에서 엔드포인트 가져오기"""
        env_key = f"{self._prefix}{key}"
        return os.getenv(env_key, "")

    def format_url(self, endpoint, **kwargs):
        """
        엔드포인트 URL 포맷팅

        Args:
            endpoint: 엔드포인트 문자열 (예: '/user/{user_id}')
            **kwargs: 치환할 변수들

        Returns:
            포맷된 URL

        Example:
            >>> api = APIEndpoints('v1')
            >>> api.format_url(api.USER_PROFILE, user_id=123)
            '/user/123'
        """
        for key, value in kwargs.items():
            endpoint = endpoint.replace(f"{{{key}}}", str(value))
        return endpoint

    # ===== 인증 (Auth) =====
    @property
    def AUTH_SIGNUP(self):
        return self._get_endpoint("AUTH_SIGNUP")

    @property
    def AUTH_LOGIN(self):
        return self._get_endpoint("AUTH_LOGIN")

    @property
    def AUTH_LOGOUT(self):
        return self._get_endpoint("AUTH_LOGOUT")

    @property
    def AUTH_REFRESH(self):
        return self._get_endpoint("AUTH_REFRESH")

    @property
    def AUTH_ME(self):
        return self._get_endpoint("AUTH_ME")

    @property
    def AUTH_UPDATE(self):
        return self._get_endpoint("AUTH_UPDATE")

    @property
    def AUTH_DELETE(self):
        return self._get_endpoint("AUTH_DELETE")

    # ===== 이미지 (Image) =====
    @property
    def IMAGE_PROFILE(self):
        return self._get_endpoint("IMAGE_PROFILE")

    @property
    def IMAGE_POST(self):
        return self._get_endpoint("IMAGE_POST")

    @property
    def IMAGE_PRODUCT(self):
        return self._get_endpoint("IMAGE_PRODUCT")

    @property
    def IMAGE_FAVICON(self):
        return self._get_endpoint("IMAGE_FAVICON")

    @property
    def IMAGE_LOGO(self):
        return self._get_endpoint("IMAGE_LOGO")

    # Deprecated aliases (이전 버전 호환용)
    @property
    def AUTH_IMAGE_UUID(self):
        """Deprecated: IMAGE_PROFILE 사용 권장"""
        return self.IMAGE_PROFILE

    @property
    def AUTH_IMAGE_USER(self):
        """Deprecated: IMAGE_PROFILE 사용 권장 (user.profile_img 값 사용)"""
        return self.IMAGE_PROFILE

    @property
    def POST_IMAGE(self):
        """Deprecated: IMAGE_POST 사용 권장"""
        return self.IMAGE_POST

    # ===== 사용자 (User) =====
    @property
    def USER_PROFILE(self):
        return self._get_endpoint("USER_PROFILE")

    @property
    def USER_FOLLOW(self):
        return self._get_endpoint("USER_FOLLOW")

    @property
    def USER_FOLLOWERS(self):
        return self._get_endpoint("USER_FOLLOWERS")

    @property
    def USER_FOLLOWING(self):
        return self._get_endpoint("USER_FOLLOWING")

    @property
    def USER_MY_FRIENDS(self):
        return self._get_endpoint("USER_MY_FRIENDS")

    # ===== 게시글 (Post) =====
    @property
    def POST_LIST(self):
        return self._get_endpoint("POST_LIST")

    @property
    def POST_CREATE(self):
        return self._get_endpoint("POST_CREATE")

    @property
    def POST_DETAIL(self):
        return self._get_endpoint("POST_DETAIL")

    @property
    def POST_UPDATE(self):
        return self._get_endpoint("POST_UPDATE")

    @property
    def POST_DELETE(self):
        return self._get_endpoint("POST_DELETE")

    @property
    def POST_LIKE(self):
        return self._get_endpoint("POST_LIKE")

    @property
    def POST_MY_POSTS(self):
        return self._get_endpoint("POST_MY_POSTS")

    # ===== 댓글 (Reply) =====
    @property
    def REPLY_LIST(self):
        return self._get_endpoint("REPLY_LIST")

    @property
    def REPLY_CREATE(self):
        return self._get_endpoint("REPLY_CREATE")

    @property
    def REPLY_DETAIL(self):
        return self._get_endpoint("REPLY_DETAIL")

    @property
    def REPLY_UPDATE(self):
        return self._get_endpoint("REPLY_UPDATE")

    @property
    def REPLY_DELETE(self):
        return self._get_endpoint("REPLY_DELETE")

    @property
    def REPLY_LIKE(self):
        return self._get_endpoint("REPLY_LIKE")

    # ===== 피드 (Feed) =====
    @property
    def FEED_PERSONALIZED(self):
        return self._get_endpoint("FEED_PERSONALIZED")

    @property
    def FEED_TRENDING(self):
        return self._get_endpoint("FEED_TRENDING")

    @property
    def FEED_EXPLORE(self):
        return self._get_endpoint("FEED_EXPLORE")

    # ===== Legacy 전용 =====
    @property
    def POSTS_LIST(self):
        """Legacy: /posts"""
        return self._get_endpoint("POSTS_LIST")

    @property
    def POSTS_COMMUNITY(self):
        """Legacy: /posts/community"""
        return self._get_endpoint("POSTS_COMMUNITY")

    @property
    def POSTS_DETAIL(self):
        """Legacy: /posts/{post_id}"""
        return self._get_endpoint("POSTS_DETAIL")


# 전역 인스턴스 (기본값: v1)
api_endpoints = APIEndpoints("v1")
legacy_endpoints = APIEndpoints("legacy")


if __name__ == "__main__":
    # 테스트
    print("=== V1 API ===")
    v1 = APIEndpoints("v1")
    print(f"AUTH_LOGIN: {v1.AUTH_LOGIN}")
    print(f"AUTH_UPDATE: {v1.AUTH_UPDATE}")
    print(f"POST_LIST: {v1.POST_LIST}")
    print(f"USER_PROFILE: {v1.format_url(v1.USER_PROFILE, user_id=123)}")

    print("\n=== Legacy API ===")
    legacy = APIEndpoints("legacy")
    print(f"AUTH_LOGIN: {legacy.AUTH_LOGIN}")
    print(f"AUTH_UPDATE: {legacy.AUTH_UPDATE}")
    print(f"POSTS_LIST: {legacy.POSTS_LIST}")
    print(f"POSTS_DETAIL: {legacy.format_url(legacy.POSTS_DETAIL, post_id=456)}")
