"""FastAPI 应用入口"""
from datetime import datetime
from pathlib import Path

import structlog
from fastapi import Depends, FastAPI, Form, Request, Response, status
from fastapi.exception_handlers import http_exception_handler
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from sqlalchemy import func, select
from sqlalchemy.orm import Session
from starlette.exceptions import HTTPException as StarletteHTTPException

from app import __version__
from app.api import meetings, scenarios, search, vocabularies
from app.api import settings as settings_routes
from app.auth import (
    SESSION_COOKIE_NAME,
    create_session_cookie,
    get_current_user,
    verify_password,
)
from app.config import get_settings
from app.database import engine, get_db
from app.models import AudioFile, Meeting, Scenario, Segment, User, Vocabulary, VocabularyTerm
from app.templating import templates

# ============================================================================
# 启动配置
# ============================================================================

settings = get_settings()
log = structlog.get_logger()

app = FastAPI(
    title="whisper-server",
    version=__version__,
    description="私人会议录音转录系统",
    docs_url="/api/docs" if settings.app_env == "development" else None,
    redoc_url=None,
)

# ============================================================================
# 模板与静态文件
# ============================================================================

BASE_DIR = Path(__file__).resolve().parent
app.mount("/static", StaticFiles(directory=str(BASE_DIR / "static")), name="static")

# 业务路由
app.include_router(meetings.router)
app.include_router(scenarios.router)
app.include_router(search.router)
app.include_router(settings_routes.router)
app.include_router(vocabularies.router)


@app.exception_handler(StarletteHTTPException)
async def _auth_aware_http_exception(request: Request, exc: StarletteHTTPException):
    """未登录访问 HTML 页面时重定向到登录页，而不是抛 401 JSON。"""
    if exc.status_code == status.HTTP_401_UNAUTHORIZED:
        return RedirectResponse(url="/login", status_code=status.HTTP_302_FOUND)
    return await http_exception_handler(request, exc)


# ============================================================================
# 基础接口
# ============================================================================

@app.get("/healthz")
def healthz(db: Session = Depends(get_db)) -> dict:
    """健康检查 - 同时验证 DB 连接"""
    try:
        db.execute(select(func.count()).select_from(User))
        db_ok = True
    except Exception as e:
        db_ok = False
        log.error("db_check_failed", error=str(e))

    return {
        "ok": db_ok,
        "version": __version__,
        "env": settings.app_env,
        "time": datetime.utcnow().isoformat() + "Z",
    }


# ============================================================================
# 首页 / Dashboard
# ============================================================================

@app.get("/", response_class=HTMLResponse)
def root(
    request: Request,
    user: User | None = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    if not user:
        return RedirectResponse(url="/login", status_code=status.HTTP_302_FOUND)

    # dashboard 统计
    scenario_count = db.scalar(select(func.count()).select_from(Scenario))
    vocab_count = db.scalar(select(func.count()).select_from(Vocabulary))
    term_count = db.scalar(select(func.count()).select_from(VocabularyTerm))

    meeting_count = db.scalar(select(func.count()).select_from(Meeting)) or 0
    transcribed_count = db.scalar(
        select(func.count()).select_from(Meeting).where(Meeting.status == "transcribed")
    ) or 0
    file_count = db.scalar(select(func.count()).select_from(AudioFile)) or 0
    char_count = db.scalar(select(func.coalesce(func.sum(func.length(Segment.text)), 0))) or 0
    duration_sec = db.scalar(
        select(func.coalesce(func.sum(Meeting.duration_sec), 0))
    ) or 0

    secs = int(duration_sec)
    if secs >= 3600:
        duration_human = f"{secs // 3600}h {secs % 3600 // 60}m"
    else:
        duration_human = f"{secs // 60}m {secs % 60}s"
    chars_human = f"{char_count / 10000:.1f} 万" if char_count >= 10000 else str(char_count)

    return templates.TemplateResponse(
        request,
        "dashboard.html",
        {
            "user": user,
            "settings": settings,
            "scenario_count": scenario_count,
            "vocab_count": vocab_count,
            "term_count": term_count,
            "meeting_count": meeting_count,
            "transcribed_count": transcribed_count,
            "file_count": file_count,
            "chars_human": chars_human,
            "duration_human": duration_human,
        },
    )


# ============================================================================
# 登录 / 登出
# ============================================================================

@app.get("/login", response_class=HTMLResponse)
def login_page(
    request: Request,
    user: User | None = Depends(get_current_user),
    error: str | None = None,
):
    if user:
        return RedirectResponse(url="/", status_code=status.HTTP_302_FOUND)
    return templates.TemplateResponse(
        request,
        "auth/login.html",
        {
            "settings": settings,
            "error": error,
        },
    )


def _cookie_secure(request: Request) -> bool:
    """HTTPS 时用 Secure cookie；局域网 HTTP 访问时不加 Secure，否则浏览器不会保存会话。"""
    proto = request.headers.get("x-forwarded-proto", "").split(",")[0].strip()
    return proto == "https" if proto else request.url.scheme == "https"


@app.post("/login")
def login_submit(
    request: Request,
    response: Response,
    username: str = Form(...),
    password: str = Form(...),
    db: Session = Depends(get_db),
):
    user = db.execute(select(User).where(User.username == username)).scalar_one_or_none()

    if not user or not verify_password(password, user.password_hash):
        log.warning("login_failed", username=username)
        return RedirectResponse(
            url="/login?error=invalid",
            status_code=status.HTTP_302_FOUND,
        )

    # 更新最后登录
    user.last_login_at = datetime.utcnow()
    db.commit()

    token = create_session_cookie(user.id)
    resp = RedirectResponse(url="/", status_code=status.HTTP_302_FOUND)
    resp.set_cookie(
        SESSION_COOKIE_NAME,
        token,
        max_age=settings.session_lifetime_days * 86400,
        httponly=True,
        samesite="lax",
        secure=_cookie_secure(request),
    )
    log.info("login_success", username=username, user_id=user.id)
    return resp


@app.post("/logout")
def logout():
    resp = RedirectResponse(url="/login", status_code=status.HTTP_302_FOUND)
    resp.delete_cookie(SESSION_COOKIE_NAME)
    return resp


# ============================================================================
# 启动事件
# ============================================================================

@app.on_event("startup")
def on_startup() -> None:
    log.info(
        "app_starting",
        version=__version__,
        env=settings.app_env,
        public_url=settings.app_public_url,
    )


@app.on_event("shutdown")
def on_shutdown() -> None:
    log.info("app_stopping")
    engine.dispose()
