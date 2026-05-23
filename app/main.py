"""FastAPI 应用入口"""
from datetime import datetime
from pathlib import Path

import structlog
from fastapi import Depends, FastAPI, Form, HTTPException, Request, Response, status
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app import __version__
from app.auth import (
    SESSION_COOKIE_NAME,
    create_session_cookie,
    get_current_user,
    require_login,
    verify_password,
)
from app.config import get_settings
from app.database import engine, get_db
from app.models import Scenario, User, Vocabulary, VocabularyTerm

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
templates = Jinja2Templates(directory=str(BASE_DIR / "templates"))
app.mount("/static", StaticFiles(directory=str(BASE_DIR / "static")), name="static")


# 模板全局变量注入（让所有模板能访问这些）
templates.env.globals["app_version"] = __version__


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

    # 简单 dashboard：场景数 / 词库数 / 词条数
    scenario_count = db.scalar(select(func.count()).select_from(Scenario))
    vocab_count = db.scalar(select(func.count()).select_from(Vocabulary))
    term_count = db.scalar(select(func.count()).select_from(VocabularyTerm))

    return templates.TemplateResponse(
        "dashboard.html",
        {
            "request": request,
            "user": user,
            "settings": settings,
            "scenario_count": scenario_count,
            "vocab_count": vocab_count,
            "term_count": term_count,
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
        "auth/login.html",
        {
            "request": request,
            "settings": settings,
            "error": error,
        },
    )


@app.post("/login")
def login_submit(
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
        secure=(settings.app_env == "production"),
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
