from cryptography.fernet import Fernet
import os
import base64
from sqlalchemy.types import TypeDecorator, String

KEY_FILE = ".secret_key"  # 또는 .env 파일, AWS SecretManager, Vault 등


def get_or_create_key():
    if os.path.exists(KEY_FILE):
        with open(KEY_FILE, "rb") as f:
            key = f.read()
    else:
        key = Fernet.generate_key()
        with open(KEY_FILE, "wb") as f:
            f.write(key)
        print("[+] 새 암호화 키가 생성되었습니다:", key.decode())
    return key


FERNET_KEY = get_or_create_key()
fernet = Fernet(FERNET_KEY)


class EncryptedString(TypeDecorator):
    impl = String

    def process_bind_param(self, value, dialect):
        if value is None:
            return None
        encrypted = fernet.encrypt(value.encode())
        return base64.urlsafe_b64encode(encrypted).decode()

    def process_result_value(self, value, dialect):
        if value is None:
            return None
        decrypted = fernet.decrypt(base64.urlsafe_b64decode(value))
        return decrypted.decode()
