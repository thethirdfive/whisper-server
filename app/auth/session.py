"""服务端 session - 用 itsdangerous 签名 cookie 携带 user_id"""
from datetime import datetime, timedelta

from fastapi import Cookie, Depends, HTTPException, Request, status
from itsdangerous import BadSignature, SignatureExpired, URLSafeTimedSerializer
from sqlalchemy.orm import Session

from app.config import get_settings
from app.database import get_db
from app.models import User

settings = get_settings()
SESSION_COOKIE_NAME = "whisper_session"


def _serializer() -> URLSafeTimedSerializer:
    return URLSafeTimedSerializer(settings.app_secret_key, salt="whisper-session-v1")


def create_session_cookie(user_id: int) -> str:
    """生成签名 token，作为 cookie 值"""
    payload = {
        "uid": user_id,
        "iat": datetime.utcnow().timestamp(),
    }
    return _serializer().dumps(payload)


def _decode_cookie(cookie: str) -> int | None:
    """从 cookie 解出 user_id，过期或无效返回 None"""
    try:
        max_age = settings.session_lifetime_days * 86400
        payload = _serializer().loads(cookie, max_age=max_age)
        return int(payload.get("uid", 0)) or None
    except (BadSignature, SignatureExpired, KeyError, ValueError):
        return None


def get_current_user(
    request: Request,
    db: Session = Depends(get_db),
    session_cookie: str | None = Cookie(None, alias=SESSION_COOKIE_NAME),
) -> User | None:
    """非强制鉴权，返回当前用户或 None"""
    if not session_cookie:
        return None
    user_id = _decode_cookie(session_cookie)
    if not user_id:
        return None
    return db.get(User, user_id)


def require_login(
    user: User | None = Depends(get_current_user),
) -> User:
    """强制要求登录"""
    if user is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="需要登录 / Login required",
        )
    return user


def require_admin(
    user: User = Depends(require_login),
) -> User:
    """强制要求管理员"""
    if user.role != "admin":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="仅管理员可操作 / Admin only",
        )
    return user
