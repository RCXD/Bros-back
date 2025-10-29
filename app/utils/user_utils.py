import random
import string
from ..models import User
from ..extensions import db

def generate_unique_nickname(base_nickname):
    """
    ✅ 닉네임 중복 방지용 랜덤 문자열 생성
    - 예: KakaoUser → KakaoUser_a3f9b2c1d4
    """
    nickname = base_nickname
    while User.query.filter_by(nickname=nickname).first():
        suffix = "_" + "".join(random.choices(string.ascii_lowercase + string.digits, k=10))
        nickname = base_nickname + suffix
    return nickname