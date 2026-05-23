"""场景浏览（只读）：预置场景及其关联词库

上传会议时选场景，会自动把其关联词库注入转录 initial_prompt。
"""
from fastapi import APIRouter, Depends, Request
from fastapi.responses import HTMLResponse
from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from app.auth import require_login
from app.database import get_db
from app.models import Scenario, User
from app.templating import templates

router = APIRouter(prefix="/scenarios", tags=["scenarios"])


@router.get("", response_class=HTMLResponse)
def list_scenarios(
    request: Request,
    user: User = Depends(require_login),
    db: Session = Depends(get_db),
):
    scenarios = db.execute(
        select(Scenario)
        .options(selectinload(Scenario.vocabularies))
        .order_by(Scenario.sort_order, Scenario.id)
    ).scalars().all()
    return templates.TemplateResponse(
        request, "scenarios/list.html", {"user": user, "scenarios": scenarios}
    )
