# whisper-server

私人会议录音转录系统 — 把音频/视频转成可搜索的结构化数据，让 Claude 通过 MCP 接管智能层。

> **当前进度**: Phase 1 Day 1-5 已完成（项目骨架 + 数据库层 + 登录页）。
> 详见下方"开发进度"。

---

## 是什么

把家里 / 公司里产生的所有口头交流（会议、培训、访谈、客户拜访）系统化沉淀：

- 🎙 本地 GPU 转录（WhisperX + community-1 + Whisper large-v3）
- 🎬 自动支持视频文件（ffmpeg 抽音轨）
- 📋 7 大行业 / 385 个预置术语自动应用到识别 prompt
- 🔍 全文搜索（SQLite FTS5）
- 🤖 MCP 接口让 Claude (Cowork / Claude Code) 远程驱动
- 🌐 中英双语 Web UI

---

## 快速开始

### 前置要求

- Docker + Docker Compose
- NVIDIA Container Toolkit (GPU 模式)
- 至少 16GB RAM, 50GB 可用磁盘
- 一个 HuggingFace token (需接受 [pyannote/speaker-diarization-community-1](https://huggingface.co/pyannote/speaker-diarization-community-1) 条款)

### 部署到 homeserver

```bash
# 1. 克隆
git clone git@github.com:你的账号/whisper-server.git
cd whisper-server

# 2. 复制环境变量
cp .env.example .env
nano .env   # 至少改这几项：APP_SECRET_KEY、ADMIN_PASSWORD_BCRYPT、HF_TOKEN

# 3. 生成 ADMIN_PASSWORD_BCRYPT
docker run --rm python:3.11 python -c \
  "import bcrypt; print(bcrypt.hashpw(b'你的密码', bcrypt.gensalt(12)).decode())"

# 4. 启动
docker compose up -d

# 5. 看日志
docker compose logs -f app

# 6. 浏览器访问
open http://localhost:18080
```

首次启动会自动：

- 跑 Alembic 迁移建表
- 加载预置场景 + 词库 (385 词条)
- 用 `ADMIN_*` 创建管理员账号

---

## 项目结构

```
whisper-server/
├── app/                       # FastAPI 应用
│   ├── main.py                # 入口
│   ├── config.py              # Pydantic Settings
│   ├── database.py            # SQLAlchemy + session
│   ├── models/                # 14 张表的 ORM
│   ├── schemas/               # Pydantic schema (Phase 1 后续补)
│   ├── api/                   # REST 路由 (Phase 1 后续补)
│   ├── auth/                  # 账密 + session
│   ├── services/              # 业务逻辑
│   ├── templates/             # Jinja2 模板
│   ├── static/                # CSS/JS
│   ├── i18n/                  # 中英文翻译
│   └── ws/                    # WebSocket
├── worker/                    # RQ worker (Phase 1 后续补)
├── migrations/                # Alembic
│   ├── env.py
│   └── versions/
│       ├── 001_initial.py     # 建所有表
│       └── 002_load_seeds.py  # 加载预置场景词库
├── seeds/
│   └── vocabulary_seed.sql    # 385 词条
├── scripts/
│   ├── create_admin.py        # 首次创建管理员
│   └── backup.sh              # 每日 DB 备份
├── docker/
│   ├── Dockerfile.app
│   ├── Dockerfile.worker
│   └── Dockerfile.backup
├── tests/
├── docker-compose.yml
├── pyproject.toml             # uv 管理依赖
├── alembic.ini
├── .env.example
└── README.md
```

---

## 开发进度

### ✅ 已完成 (Day 1-5)

- 项目骨架与目录结构
- docker-compose.yml + 三个 Dockerfile
- .env.example 含所有可配置项
- 15 张表的 SQLAlchemy ORM 模型（`app/models/`）
- Alembic 初始化 + 001 建表迁移 + 002 词库 seed 加载
- 首次启动自动创建管理员（基于 .env 的 ADMIN_*）
- FastAPI app 主程序 + 配置 + DB session
- 账号密码登录 (bcrypt + 服务端 session)
- 健康检查接口 `/healthz`
- 登录页 + 占位的首页
- 每日 SQLite 备份脚本

### ✅ 已完成 (Day 6-7)

- 词库管理 UI：列表 / 详情 / 词条增删改、自定义词库（预置词库受保护）
- 上传向导：多文件、场景选择、自定义提示词，保存到 HDD recordings 并入队
- 会议列表 / 详情页（含转录文本、说话人、initial_prompt 预览）
- WhisperX 转录 worker（`worker/jobs/process_meeting.py`）：
  ffprobe → 视频抽轨 → 16k 合并 → 场景词库拼 prompt → 转录 + 对齐 + 说话人分离 → 入库
  （代码完成并通过编排测试；首次实跑会下载 large-v3 等模型）
- htmx 状态轮询（转录完成自动刷新展示结果）
- 未登录访问 HTML 页自动跳登录页
- 修复：`.gitignore` 的 `models/` 误伤 ORM 包；`.env` bcrypt 含 `$` 被 compose
  env_file 插值损坏；`BACKUP_CRON_SCHEDULE` 未加引号致 `source .env` 报错；
  RQ 2.x 移除 `Connection`；Starlette 新版 `TemplateResponse` 签名

### 🚧 进行中 / 下一步

- [ ] 场景管理 / 设置页 UI
- [ ] 全文搜索（FTS5；注意 unicode61 不切分中文，需 trigram/CJK tokenizer）
- [ ] 说话人重命名、Word/产物导出
- [ ] MCP server (Phase 3)
- [ ] Google Drive 集成 (Phase 2)
- [ ] 双语 i18n 完整翻译
- [ ] Watch folder (Phase 4)

详见 [设计文档](docs/design.md)。

---

## 常用命令

```bash
# 重启某个容器
docker compose restart app
docker compose restart worker

# 看实时日志
docker compose logs -f app worker

# 进容器
docker compose exec app bash

# 跑迁移
docker compose exec app alembic upgrade head

# 创建新迁移
docker compose exec app alembic revision --autogenerate -m "你的描述"

# 重置数据库（开发环境！）
docker compose down -v
rm -rf /data/whisper/db/*
docker compose up -d

# 手动触发备份
docker compose exec backup-cron /backup.sh
```

---

## 部署到 homeserver + 接入 VPS 公网

完整步骤见 [docs/deployment.md](docs/deployment.md)（待补）：

1. 在你 homeserver 现有 `frpc.toml` 追加一段
2. 阿里云 VPS 的 Nginx Proxy Manager 加 host `whisper.abowk.cn` → `127.0.0.1:18080`
3. 启 SSL (Let's Encrypt)
4. 加 WebSocket 支持的 Advanced 配置

---

## 许可

Private. © 2026 Ethan.
