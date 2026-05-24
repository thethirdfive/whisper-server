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
- 场景浏览页（含关联词库）、设置 / 系统信息页（只读）
- WhisperX 转录 worker（`worker/jobs/process_meeting.py`）：
  ffprobe → 视频抽轨 → 16k 合并 → 场景词库拼 prompt → 转录 + 对齐 + 说话人分离 → 入库
  （代码完成并通过编排测试；首次实跑会下载 large-v3 等模型）
- htmx 状态轮询（转录完成自动刷新展示结果）
- 未登录访问 HTML 页自动跳登录页
- 修复：`.gitignore` 的 `models/` 误伤 ORM 包；`.env` bcrypt 含 `$` 被 compose
  env_file 插值损坏；`BACKUP_CRON_SCHEDULE` 未加引号致 `source .env` 报错；
  RQ 2.x 移除 `Connection`；Starlette 新版 `TemplateResponse` 签名

### ✅ 已完成 (Day 8)

- 说话人分离 4 种模式（上传时按场景选）：
  - `channels` 按声道拆分 —— 双声道/每人一个麦的访谈、对话，**无需联网模型、离线可用**
  - `auto` / `count` —— 同声道多人，用 pyannote 自动估计或指定人数（需 gated 模型）
  - `off` 不分离
  - 诊断脚本 `scripts/check_diarization.py` 检查 gated 模型是否就绪
- 设置页可在线编辑：运营类配置写入 `settings` 表，运行时**覆盖 .env**（app+worker 共用）；
  HF_TOKEN / 密钥等敏感项只读打码，写操作限管理员

### ✅ 已完成 (Day 9)

- 大文件上传重构（解决 WAN 上传卡死/无进度）：
  - **分块断点续传**：每块 5MB（远小于 nginx `client_max_body_size`/超时），
    `POST /meetings/draft` 建草稿 → `PUT .../chunk?offset=` 逐块（偏移不符 409 自动续传）
    → `POST .../finalize` 入队；无 JS 时回退原整文件 POST
  - **后台异步 + 进度托盘**：`static/upload.js` 全局上传管理器，右下角进度条/速度，
    失败自动重试，可排队多场会议；导航用 htmx-boost 只换 `#page`，上传不中断
  - 刷新后用 localStorage 提示「重选文件续传」（浏览器无法持久化 File 对象）
  - CUDA OOM 修复：`whisper_batch_size` 可配（8GB 卡默认 4）+ OOM 自动降批 + 阶段间释放显存

### ✅ 已完成 (Day 10)

- 转录后整理（方案一：Claude Code + MCP）—— 见 [docs/organize-with-claude-code.md](docs/organize-with-claude-code.md)：
  - 每场景一套**整理模板**（场景页可编辑，留空用内置默认），生成**HTML 报告**
  - 会议详情页「生成报告」→ 进整理队列；报告可在线查看/下载；生成后 **Bark 通知**
  - **MCP server**（`mcp_server/server.py`，stdio 直连同一 SQLite）：list_pending_reports /
    get_meeting / claim_report / submit_report / report_failed
  - `.mcp.json` + `.venv-mcp` 让本机 Claude Code 即插即用；用 `/schedule` 或 `/loop` 定期整理
  - 整理器走 Claude Max 订阅，几乎零额外费用；方案二（LLM API）可复用同一队列/模板/产出

### ✅ 已完成 (Day 11)

- Google Drive 拉取（Picker）：网页里用 Google Picker 选 Drive 文件 → 服务端用短期
  token **直接从 Drive 下载**（机房↔Google，绕开 WAN 上行，适合大文件）→ 入队转录。
  - 配置：在「设置」填 `GDRIVE_OAUTH_CLIENT_ID` + `GDRIVE_API_KEY`（GCP 建 OAuth Web
    客户端 + API Key，启用 Picker/Drive API）；未配置则上传页不显示该入口
  - app 容器经本机代理出站（国内访问 googleapis.com 必需，复用 worker 的代理设置）

### ✅ 已完成 (Day 12)

- 视觉改版：**深空暗色 · 青蓝霓虹**主题 + 波形 Logo（SVG，含 favicon）。
  - `static/style.css` 统一覆盖 Tailwind 工具类（中性色→暗色玻璃、blue→青蓝渐变发光），
    所有页面一次性变暗，无需逐个改模板；玻璃拟态卡片、径向光晕背景、细网格、发光强调。
  - 重做登录页/首页 hero（渐变标题、波形装饰、能力一览）、品牌文案、上传托盘暗色化。

### ✅ 已完成 (Day 13)

- 全文搜索：SQLite **FTS5 + trigram 分词器**（替换 001 的 unicode61，支持中文子串），
  bm25 排序 + snippet 高亮；触发器与转录自动同步；<3 字查询 LIKE 兜底；
  顶栏搜索框 + `/search` 页（按会议分组、带时间戳定位）。几百场会议量级足够，零外部服务。

### ✅ 已完成 (Day 14)

- 首页语料总览：会议总数 / 转录字数 / 处理音频时长 / 音视频文件数。
- 会议列表：整理状态列 + 按场景/公司/时间筛选 + 分页（每页 20）。
- 会议详情：导出转录 TXT、报告导出 PDF（HTML 打开后唤起浏览器打印→另存 PDF）、下载 HTML。
- 搜索：按场景/公司/时间筛选；点命中片段跳转到转录对应段落并高亮（`#seg-{id}`）。

### 🚧 进行中 / 下一步

- [ ] 场景↔词库关联在线编辑（设置项在线修改已完成）
- [ ] 说话人重命名、Word/产物导出
- [ ] MCP server (Phase 3)
- [ ] Google Drive 集成 (Phase 2)
- [ ] 双语 i18n 完整翻译
- [ ] Watch folder (Phase 4)

详见 [设计文档](docs/design.md)。

---

## 说话人分离 (Speaker Diarization)

上传会议时在「说话人分离」里选模式：

| 模式 | 适用 | 是否需要联网模型 |
|------|------|------------------|
| 按声道拆分 `channels` | 立体声录音、每人占一个声道（双麦访谈、对话） | **否，离线可用** |
| 自动估计人数 `auto` | 同一声道里多人说话 | 是（pyannote gated） |
| 指定人数 `count` | 同上，已知人数/范围时更准 | 是（pyannote gated） |
| 不分离 `off` | 单人录音 / 不需要区分 | 否 |

### 让 pyannote gated 模型可用（auto / count 模式）

`pyannote/speaker-diarization-community-1` 是 **gated（受限）模型**，要用 auto/count
需满足两点：

1. **接受条款**：用 `.env` 里 `HF_TOKEN` 对应的 HuggingFace 账号登录，打开
   https://hf.co/pyannote/speaker-diarization-community-1 点 **Agree and access repository**。
2. **能下到文件**：本部署默认 `HF_ENDPOINT=https://hf-mirror.com`，但**镜像不给下
   gated 仓库的权重文件**（实测：元数据能读、文件下不动）。所以 worker 需要走能直连
   huggingface.co 的网络。

本机的做法（已配置）——让 **worker 经本机 mihomo 代理直连真 huggingface.co**：

```ini
# .env（仅 worker 生效，见 docker-compose.yml 的 environment 段）
WORKER_HF_ENDPOINT=https://huggingface.co
WORKER_HF_PROXY=http://host.docker.internal:7890   # 本机代理端口
```

> compose 里 worker 已加 `extra_hosts: host.docker.internal:host-gateway`，让容器能
> 通过该名字访问宿主机（容器 DNS 会被透明代理 fake-ip 劫持，故用 extra_hosts 固定）。
> 不需要代理的环境把这两个变量留空即可，worker 自动回退到 `hf-mirror.com`。

配好后模型会缓存到 `HF_HOME=/data/whisper/models/hf`（持久化卷），之后即使代理不在也能
从缓存加载。验证：

```bash
docker compose exec worker python scripts/check_diarization.py
# 看到 “说话人分离已就绪 ✅” 即可
```

> 实在没有可用代理 → 直接用 **按声道拆分** 模式（双声道录音完全不依赖这个模型）。

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
