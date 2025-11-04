# 단순 메모리 블랙리스트
jwt_blacklist = set()

def add_to_blacklist(jti: str):
    jwt_blacklist.add(jti)