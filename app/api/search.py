"""全文搜索页：搜所有会议的转录内容 + 标题/公司/标签。"""
from fastapi import APIRouter, Depends, Request
from fastapi.responses import HTMLResponse
from sqlalchemy.orm import Session

from app.auth import require_login
from app.database import get_db
from app.models import User
from app.services import search as search_svc
from app.templating import templates

router = APIRouter(tags=["search"])


@router.get("/search", response_class=HTMLResponse)
def search_page(
    request: Request,
    q: str = "",
    user: User = Depends(require_login),
    db: Session = Depends(get_db),
):
    res = search_svc.search(db, q)
    return templates.TemplateResponse(request, "search.html", {"user": user, **res})
