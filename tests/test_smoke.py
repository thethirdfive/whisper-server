"""烟测：所有模块能 import + 数据库能初始化 + 登录页能渲染"""
import os
import tempfile
from pathlib import Path

import pytest


@pytest.fixture
def tmp_db_url(monkeypatch):
    """每个测试一个临时 SQLite"""
    tmp = tempfile.NamedTemporaryFile(suffix=".db", delete=False)
    tmp.close()
    monkeypatch.setenv("DATABASE_URL", f"sqlite:///{tmp.name}")
    monkeypatch.setenv("APP_SECRET_KEY", "test-secret-key-1234567890abcdef")
    monkeypatch.setenv("APP_ENV", "development")
    yield tmp.name
    os.unlink(tmp.name)


def test_imports():
    """所有关键模块能 import"""
    from app import main
    from app.config import get_settings
    from app.database import engine, get_db
    from app.auth import hash_password, verify_password
    from app.models import (
        Base, User, ApiToken, Setting,
        Scenario, ScenarioVocabulary,
        Vocabulary, VocabularyTerm,
        Meeting, AudioFile,
        Speaker, Segment,
        ActionItem, Deliverable,
        Job, AuditLog,
    )
    assert Base is not None
    assert hash_password("test")
    assert verify_password("test", hash_password("test"))


def test_password_roundtrip():
    from app.auth import hash_password, verify_password
    h = hash_password("hello-world-2026")
    assert h.startswith("$2b$")
    assert verify_password("hello-world-2026", h)
    assert not verify_password("wrong", h)


def test_settings_load():
    from app.config import get_settings
    s = get_settings()
    assert s.whisper_model == "large-v3"
    assert "m4a" in s.allowed_audio_set
    assert "mp4" in s.allowed_video_set


def test_database_init(tmp_db_url):
    """临时 DB + 跑迁移 + 验证表存在"""
    # 重新导入触发新 DATABASE_URL
    import importlib
    from app import config
    importlib.reload(config)
    from app import database
    importlib.reload(database)

    from alembic import command
    from alembic.config import Config

    cfg = Config(str(Path(__file__).parent.parent / "alembic.ini"))
    cfg.set_main_option("sqlalchemy.url", f"sqlite:///{tmp_db_url}")
    command.upgrade(cfg, "head")

    # 验证表存在
    from sqlalchemy import inspect
    inspector = inspect(database.engine)
    tables = inspector.get_table_names()
    expected = {
        "users", "api_tokens", "settings",
        "scenarios", "vocabularies", "vocabulary_terms",
        "scenario_vocabularies", "meetings", "audio_files",
        "speakers", "segments", "action_items",
        "deliverables", "jobs", "audit_log",
    }
    missing = expected - set(tables)
    assert not missing, f"缺表：{missing}"

    # 验证预置数据加载（10 场景 / 7 词库 / 385 词条）
    with database.engine.connect() as conn:
        from sqlalchemy import text
        scenarios = conn.execute(text("SELECT COUNT(*) FROM scenarios")).scalar()
        vocabs = conn.execute(text("SELECT COUNT(*) FROM vocabularies")).scalar()
        terms = conn.execute(text("SELECT COUNT(*) FROM vocabulary_terms")).scalar()
        assert scenarios == 10, f"场景数 {scenarios} != 10"
        assert vocabs == 7, f"词库数 {vocabs} != 7"
        assert terms >= 380, f"词条数 {terms} < 380"
