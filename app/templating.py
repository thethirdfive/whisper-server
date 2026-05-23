"""共享的 Jinja2Templates 实例

放在独立模块里，让 app.main 与各个 api 路由共用同一个 templates，避免循环导入。
settings 注入为全局变量，模板里可直接用 {{ settings.xxx }}；request 由
TemplateResponse(request, ...) 自动注入；user / 页面数据按需在 context 传。
"""
from pathlib import Path

from fastapi.templating import Jinja2Templates

from app import __version__
from app.config import get_settings

BASE_DIR = Path(__file__).resolve().parent
templates = Jinja2Templates(directory=str(BASE_DIR / "templates"))
templates.env.globals["app_version"] = __version__
templates.env.globals["settings"] = get_settings()
