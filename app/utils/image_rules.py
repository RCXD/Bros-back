# utils/image_rules.py
"""
 이미지 종류별 리사이즈 / 용량 제한 / 포맷 규칙
"""
IMAGE_RULES = {
    "profile": {
        "max_size": (300, 300),
        "max_bytes": 500 * 1024  # 500KB
    },
    "post": {
        "max_size": None,  # 크기 제한 없음
        "max_bytes": 10 * 1024 * 1024  # 10MB
    },
    "reply": {
        "max_size": (960, 600),
        "max_bytes": 3 * 1024 * 1024  # 3MB
    },
    "emoticon": {
        "max_size": (128, 128),
        "max_bytes": 500 * 1024  # 500KB
    },
    "default": {
        "max_size": (1024, 1024),
        "max_bytes": 2 * 1024 * 1024  # 2MB
    },
}