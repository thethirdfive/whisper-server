"""密码哈希与校验"""
import bcrypt


def hash_password(password: str) -> str:
    """生成 bcrypt 哈希（cost=12）"""
    return bcrypt.hashpw(password.encode(), bcrypt.gensalt(12)).decode()


def verify_password(password: str, password_hash: str) -> bool:
    """校验密码"""
    try:
        return bcrypt.checkpw(password.encode(), password_hash.encode())
    except (ValueError, AttributeError):
        return False
