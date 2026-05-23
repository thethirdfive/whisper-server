"""词库管理 UI 与增删改

- 列表：所有词库（预置 builtin 在前）+ 词条数
- 详情：词库元信息 + 词条表格，支持新增/编辑/删除词条
- 词库本身：可新建自定义词库；预置(builtin)词库不允许删除，但允许增删词条
读取需登录，写操作需管理员。所有写操作用 PRG（POST→Redirect→GET）避免重复提交。
"""
from fastapi import APIRouter, Depends, Form, HTTPException, Request, status
from fastapi.responses import HTMLResponse, RedirectResponse
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.auth import require_admin, require_login
from app.database import get_db
from app.models import User, Vocabulary, VocabularyTerm
from app.templating import templates

router = APIRouter(prefix="/vocabularies", tags=["vocabularies"])


def _redirect(url: str) -> RedirectResponse:
    return RedirectResponse(url=url, status_code=status.HTTP_303_SEE_OTHER)


@router.get("", response_class=HTMLResponse)
def list_vocabularies(
    request: Request,
    user: User = Depends(require_login),
    db: Session = Depends(get_db),
    msg: str | None = None,
    error: str | None = None,
):
    vocabs = db.execute(
        select(Vocabulary).order_by(Vocabulary.builtin.desc(), Vocabulary.code)
    ).scalars().all()
    counts = dict(
        db.execute(
            select(VocabularyTerm.vocabulary_id, func.count())
            .group_by(VocabularyTerm.vocabulary_id)
        ).all()
    )
    return templates.TemplateResponse(
        request,
        "vocabularies/list.html",
        {
            "user": user,
            "vocabs": vocabs,
            "counts": counts,
            "msg": msg,
            "error": error,
        },
    )


@router.post("")
def create_vocabulary(
    user: User = Depends(require_admin),
    db: Session = Depends(get_db),
    code: str = Form(...),
    name_zh: str = Form(...),
    name_en: str = Form(...),
    industry: str = Form(""),
    description_zh: str = Form(""),
    description_en: str = Form(""),
):
    code = code.strip()
    if not code or not name_zh.strip() or not name_en.strip():
        return _redirect("/vocabularies?error=词库代码与中英文名称均必填")
    exists = db.scalar(select(Vocabulary).where(Vocabulary.code == code))
    if exists:
        return _redirect(f"/vocabularies?error=词库代码 {code} 已存在")
    vocab = Vocabulary(
        code=code,
        name_zh=name_zh.strip(),
        name_en=name_en.strip(),
        industry=industry.strip() or None,
        description_zh=description_zh.strip() or None,
        description_en=description_en.strip() or None,
        builtin=False,
    )
    db.add(vocab)
    db.commit()
    return _redirect(f"/vocabularies/{vocab.id}?msg=词库已创建")


@router.get("/{vocab_id}", response_class=HTMLResponse)
def vocabulary_detail(
    vocab_id: int,
    request: Request,
    user: User = Depends(require_login),
    db: Session = Depends(get_db),
    msg: str | None = None,
    error: str | None = None,
):
    vocab = db.get(Vocabulary, vocab_id)
    if not vocab:
        raise HTTPException(status_code=404, detail="词库不存在")
    terms = db.execute(
        select(VocabularyTerm)
        .where(VocabularyTerm.vocabulary_id == vocab_id)
        .order_by(VocabularyTerm.sort_order, VocabularyTerm.id)
    ).scalars().all()
    return templates.TemplateResponse(
        request,
        "vocabularies/detail.html",
        {
            "user": user,
            "vocab": vocab,
            "terms": terms,
            "msg": msg,
            "error": error,
        },
    )


@router.post("/{vocab_id}")
def update_vocabulary(
    vocab_id: int,
    user: User = Depends(require_admin),
    db: Session = Depends(get_db),
    name_zh: str = Form(...),
    name_en: str = Form(...),
    industry: str = Form(""),
    description_zh: str = Form(""),
    description_en: str = Form(""),
):
    vocab = db.get(Vocabulary, vocab_id)
    if not vocab:
        raise HTTPException(status_code=404, detail="词库不存在")
    vocab.name_zh = name_zh.strip() or vocab.name_zh
    vocab.name_en = name_en.strip() or vocab.name_en
    vocab.industry = industry.strip() or None
    vocab.description_zh = description_zh.strip() or None
    vocab.description_en = description_en.strip() or None
    db.commit()
    return _redirect(f"/vocabularies/{vocab_id}?msg=词库信息已更新")


@router.post("/{vocab_id}/delete")
def delete_vocabulary(
    vocab_id: int,
    user: User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    vocab = db.get(Vocabulary, vocab_id)
    if not vocab:
        raise HTTPException(status_code=404, detail="词库不存在")
    if vocab.builtin:
        return _redirect(f"/vocabularies/{vocab_id}?error=预置词库不可删除")
    db.delete(vocab)  # 词条经 ORM cascade 一并删除
    db.commit()
    return _redirect("/vocabularies?msg=词库已删除")


@router.post("/{vocab_id}/terms")
def add_term(
    vocab_id: int,
    user: User = Depends(require_admin),
    db: Session = Depends(get_db),
    term_zh: str = Form(""),
    term_en: str = Form(""),
    pinyin: str = Form(""),
    aliases: str = Form(""),
    note: str = Form(""),
):
    vocab = db.get(Vocabulary, vocab_id)
    if not vocab:
        raise HTTPException(status_code=404, detail="词库不存在")
    if not term_zh.strip() and not term_en.strip():
        return _redirect(f"/vocabularies/{vocab_id}?error=中文或英文术语至少填一个")
    term = VocabularyTerm(
        vocabulary_id=vocab_id,
        term_zh=term_zh.strip() or None,
        term_en=term_en.strip() or None,
        pinyin=pinyin.strip() or None,
        aliases=aliases.strip() or None,
        note=note.strip() or None,
    )
    db.add(term)
    db.commit()
    return _redirect(f"/vocabularies/{vocab_id}?msg=词条已添加")


@router.post("/{vocab_id}/terms/{term_id}")
def update_term(
    vocab_id: int,
    term_id: int,
    user: User = Depends(require_admin),
    db: Session = Depends(get_db),
    term_zh: str = Form(""),
    term_en: str = Form(""),
    pinyin: str = Form(""),
    aliases: str = Form(""),
    note: str = Form(""),
):
    term = db.get(VocabularyTerm, term_id)
    if not term or term.vocabulary_id != vocab_id:
        raise HTTPException(status_code=404, detail="词条不存在")
    if not term_zh.strip() and not term_en.strip():
        return _redirect(f"/vocabularies/{vocab_id}?error=中文或英文术语至少填一个")
    term.term_zh = term_zh.strip() or None
    term.term_en = term_en.strip() or None
    term.pinyin = pinyin.strip() or None
    term.aliases = aliases.strip() or None
    term.note = note.strip() or None
    db.commit()
    return _redirect(f"/vocabularies/{vocab_id}?msg=词条已更新")


@router.post("/{vocab_id}/terms/{term_id}/delete")
def delete_term(
    vocab_id: int,
    term_id: int,
    user: User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    term = db.get(VocabularyTerm, term_id)
    if not term or term.vocabulary_id != vocab_id:
        raise HTTPException(status_code=404, detail="词条不存在")
    db.delete(term)
    db.commit()
    return _redirect(f"/vocabularies/{vocab_id}?msg=词条已删除")
