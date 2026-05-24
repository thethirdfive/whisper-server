"""全文搜索页：搜所有会议的转录内容 + 标题/公司/标签，可按场景/公司/时间筛选。"""
from fastapi import APIRouter, Depends, Request
from fastapi.responses import HTMLResponse
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.auth import require_login
from app.database import get_db
from app.models import Meeting, Scenario, User
from app.services import search as search_svc
from app.templating import templates

router = APIRouter(tags=["search"])


@router.get("/search", response_class=HTMLResponse)
def search_page(
    request: Request,
    q: str = "",
    scenario_id: str = "",
    company: str = "",
    date_from: str = "",
    date_to: str = "",
    user: User = Depends(require_login),
    db: Session = Depends(get_db),
):
    res = search_svc.search(
        db, q, scenario_id=scenario_id, company=company,
        date_from=date_from, date_to=date_to,
    )
    scenarios = db.execute(
        select(Scenario).order_by(Scenario.sort_order, Scenario.id)
    ).scalars().all()
    companies = [
        c for (c,) in db.execute(
            select(Meeting.company).where(Meeting.company.is_not(None)).distinct()
            .order_by(Meeting.company)
        ).all()
    ]
    return templates.TemplateResponse(
        request, "search.html",
        {
            "user": user, **res, "scenarios": scenarios, "companies": companies,
            "f": {"scenario_id": scenario_id, "company": company,
                  "date_from": date_from, "date_to": date_to},
        },
    )
