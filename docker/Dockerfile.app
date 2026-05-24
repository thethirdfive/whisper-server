# whisper-server app 镜像
# 只跑 FastAPI，无需 GPU，镜像保持小

FROM python:3.11-slim AS base

# 基础系统依赖（含 weasyprint 渲染 PDF 所需的 pango/cairo + 中文字体）
RUN apt-get update && apt-get install -y --no-install-recommends \
        curl \
        ca-certificates \
        sqlite3 \
        gettext \
        libpango-1.0-0 \
        libpangoft2-1.0-0 \
        libharfbuzz0b \
        libfontconfig1 \
        libcairo2 \
        fonts-wqy-zenhei \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# 用 uv 管理依赖（更快）
RUN pip install --no-cache-dir uv

# 先复制 pyproject 让构建缓存生效
COPY pyproject.toml ./

# 安装应用层依赖（不含 worker / dev）
RUN uv pip install --system --no-cache \
        "fastapi[all]>=0.115.0" \
        "uvicorn[standard]>=0.32.0" \
        "sqlalchemy>=2.0.35" \
        "alembic>=1.13.0" \
        "aiosqlite>=0.20.0" \
        "bcrypt>=4.2.0" \
        "itsdangerous>=2.2.0" \
        "jinja2>=3.1.4" \
        "python-multipart>=0.0.12" \
        "babel>=2.16.0" \
        "pydantic>=2.9.0" \
        "pydantic-settings>=2.5.0" \
        "rq>=1.16.0" \
        "redis>=5.1.0" \
        "httpx>=0.27.0" \
        "python-dotenv>=1.0.1" \
        "structlog>=24.4.0" \
        "tenacity>=9.0.0" \
        "weasyprint>=62.0" \
        "mcp>=1.2.0"

# 复制应用代码
COPY app/ /app/app/
COPY worker/ /app/worker/
COPY mcp_server/ /app/mcp_server/
COPY migrations/ /app/migrations/
COPY seeds/ /app/seeds/
COPY scripts/ /app/scripts/
COPY alembic.ini /app/

# 入口脚本：跑迁移 + 创建管理员 + 启 uvicorn
COPY docker/entrypoint-app.sh /entrypoint.sh
RUN chmod +x /entrypoint.sh

EXPOSE 8000

ENV PYTHONUNBUFFERED=1
ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONPATH=/app

ENTRYPOINT ["/entrypoint.sh"]
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000", "--workers", "2"]
