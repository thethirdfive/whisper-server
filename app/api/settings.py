"""设置 / 系统信息（只读概览）

运行配置当前以 .env 为准；settings 表是预留的可视化入口，这里只读展示。
"""
from fastapi import APIRouter, Depends, Request
from fastapi.responses import HTMLResponse
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.auth import require_login
from app.database import get_db
from app.models import Meeting, Scenario, Setting, User, Vocabulary, VocabularyTerm
from app.templating import templates

router = APIRouter(prefix="/settings", tags=["settings"])


@router.get("", response_class=HTMLResponse)
def settings_page(
    request: Request,
    user: User = Depends(require_login),
    db: Session = Depends(get_db),
):
    rows = db.execute(select(Setting).order_by(Setting.key)).scalars().all()
    stats = {
        "scenarios": db.scalar(select(func.count()).select_from(Scenario)),
        "vocabs": db.scalar(select(func.count()).select_from(Vocabulary)),
        "terms": db.scalar(select(func.count()).select_from(VocabularyTerm)),
        "meetings": db.scalar(select(func.count()).select_from(Meeting)),
    }
    return templates.TemplateResponse(
        request, "settings/index.html", {"user": user, "rows": rows, "stats": stats}
    )
