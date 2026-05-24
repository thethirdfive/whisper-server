"""场景浏览 + 每场景整理模板编辑

上传会议时选场景 → 自动把其关联词库注入转录 initial_prompt；
转录后整理时 → 用该场景的整理模板（无则用内置默认）指导生成 HTML 报告。
"""
from fastapi import APIRouter, Depends, Form, HTTPException, Request, status
from fastapi.responses import HTMLResponse, RedirectResponse
from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from app.auth import require_login
from app.database import get_db
from app.models import ReportTemplate, Scenario, User
from app.services import reports as reports_svc
from app.templating import templates

router = APIRouter(prefix="/scenarios", tags=["scenarios"])


@router.get("", response_class=HTMLResponse)
def list_scenarios(
    request: Request,
    user: User = Depends(require_login),
    db: Session = Depends(get_db),
    msg: str | None = None,
):
    scenarios = db.execute(
        select(Scenario)
        .options(selectinload(Scenario.vocabularies))
        .order_by(Scenario.sort_order, Scenario.id)
    ).scalars().all()
    custom = {
        t.scenario_id
        for t in db.execute(select(ReportTemplate.scenario_id)).scalars().all()
        if t is not None
    }
    return templates.TemplateResponse(
        request, "scenarios/list.html",
        {"user": user, "scenarios": scenarios, "custom_template_ids": custom, "msg": msg},
    )


@router.get("/{scenario_id}/template", response_class=HTMLResponse)
def edit_template(
    scenario_id: int,
    request: Request,
    user: User = Depends(require_login),
    db: Session = Depends(get_db),
    saved: str | None = None,
):
    sc = db.get(Scenario, scenario_id)
    if not sc:
        raise HTTPException(status_code=404, detail="场景不存在")
    tpl = db.execute(
        select(ReportTemplate).where(ReportTemplate.scenario_id == scenario_id)
    ).scalar_one_or_none()
    return templates.TemplateResponse(
        request, "scenarios/template.html",
        {
            "user": user,
            "scenario": sc,
            "instructions": tpl.instructions if tpl else "",
            "has_custom": tpl is not None,
            "default_template": reports_svc.DEFAULT_TEMPLATE,
            "saved": saved,
        },
    )


@router.post("/{scenario_id}/template")
def save_template(
    scenario_id: int,
    user: User = Depends(require_login),
    db: Session = Depends(get_db),
    instructions: str = Form(""),
):
    if user.role != "admin":
        return RedirectResponse("/scenarios?msg=仅管理员可改模板", status_code=status.HTTP_303_SEE_OTHER)
    sc = db.get(Scenario, scenario_id)
    if not sc:
        raise HTTPException(status_code=404, detail="场景不存在")
    tpl = db.execute(
        select(ReportTemplate).where(ReportTemplate.scenario_id == scenario_id)
    ).scalar_one_or_none()
    text = instructions.strip()
    if not text:
        # 清空 = 删除自定义，回退内置默认
        if tpl:
            db.delete(tpl)
            db.commit()
        return RedirectResponse(
            f"/scenarios/{scenario_id}/template?saved=1", status_code=status.HTTP_303_SEE_OTHER
        )
    if tpl:
        tpl.instructions = text
        tpl.updated_by = user.id
    else:
        db.add(ReportTemplate(
            scenario_id=scenario_id, name=sc.name_zh, instructions=text, updated_by=user.id,
        ))
    db.commit()
    return RedirectResponse(
        f"/scenarios/{scenario_id}/template?saved=1", status_code=status.HTTP_303_SEE_OTHER
    )
