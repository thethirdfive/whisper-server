"""设置 / 系统信息

运营类配置可在线编辑（存 settings 表，运行时覆盖 .env）；HF_TOKEN / 密钥等
敏感项只读打码展示。写操作限管理员。
"""
from fastapi import APIRouter, Depends, Request, status
from fastapi.responses import HTMLResponse, RedirectResponse
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.auth import require_login
from app.database import get_db
from app.models import Meeting, Scenario, User, Vocabulary, VocabularyTerm
from app.services import settings_store
from app.templating import templates

router = APIRouter(prefix="/settings", tags=["settings"])


def _stats(db: Session) -> dict:
    return {
        "scenarios": db.scalar(select(func.count()).select_from(Scenario)),
        "vocabs": db.scalar(select(func.count()).select_from(Vocabulary)),
        "terms": db.scalar(select(func.count()).select_from(VocabularyTerm)),
        "meetings": db.scalar(select(func.count()).select_from(Meeting)),
    }


@router.get("", response_class=HTMLResponse)
def settings_page(
    request: Request,
    user: User = Depends(require_login),
    db: Session = Depends(get_db),
    saved: str | None = None,
    error: str | None = None,
):
    return templates.TemplateResponse(
        request,
        "settings/index.html",
        {
            "user": user,
            "groups": settings_store.grouped(),
            "values": settings_store.effective_all(db),
            "overridden": settings_store.overridden_keys(db),
            "sensitive": settings_store.sensitive_display(),
            "stats": _stats(db),
            "saved": saved,
            "error": error,
        },
    )


@router.post("")
async def settings_save(
    request: Request,
    user: User = Depends(require_login),
    db: Session = Depends(get_db),
):
    if user.role != "admin":
        return RedirectResponse(
            "/settings?error=仅管理员可修改设置", status_code=status.HTTP_303_SEE_OTHER
        )
    form = dict(await request.form())
    errors = settings_store.save(db, form, user.id)
    if errors:
        return RedirectResponse(
            f"/settings?error=以下项取值非法：{', '.join(errors)}",
            status_code=status.HTTP_303_SEE_OTHER,
        )
    return RedirectResponse("/settings?saved=1", status_code=status.HTTP_303_SEE_OTHER)


@router.post("/reset/{key}")
def settings_reset(
    key: str,
    user: User = Depends(require_login),
    db: Session = Depends(get_db),
):
    if user.role != "admin":
        return RedirectResponse(
            "/settings?error=仅管理员可修改设置", status_code=status.HTTP_303_SEE_OTHER
        )
    settings_store.reset(db, key)
    return RedirectResponse("/settings?saved=1", status_code=status.HTTP_303_SEE_OTHER)
