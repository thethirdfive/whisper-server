# whisper-server

私人会议录音转录系统 — 把音频/视频转成可搜索的结构化数据，并让 Claude 经 **MCP** 接管「整理成报告」的智能层。

线上（仅本人）：`https://whisper.abowk.cn`，本地发布于 `127.0.0.1:18080`。

本文档覆盖：[功能特性](#功能特性) · [所用技术](#所用技术技术栈) · [技术原理](#技术原理架构与数据流) · [操作流程](#操作流程) · [版本控制](#版本控制与变更记录)。

---

## 是什么

把家里 / 公司里产生的所有口头交流（会议、培训、访谈、客户拜访）系统化沉淀为「可检索的智慧」：

- 🎙 本地 GPU 转录（WhisperX + Whisper large-v3 + pyannote community-1）
- 🎬 自动支持视频文件（ffmpeg 抽音轨）
- 📋 7 大行业 / 385 个预置术语按场景拼进识别 prompt，提升专有名词准确率
- 🗣 4 种说话人分离模式（含离线的按声道拆分）
- 🔍 中文可用的全文搜索（SQLite FTS5 + trigram）
- 🤖 MCP 接口让 Claude（Claude Code）把转录整理成 HTML 报告（走 Max 订阅，零额外费用）
- ⬆ 大文件分块断点续传 + Google Drive 直拉
- 🌐 中英双语界面 · 深空暗色霓虹主题

---

## 功能特性

| 模块 | 能力 |
|------|------|
| 鉴权 | 账号密码登录（bcrypt）+ 服务端签名 session；未登录访问 HTML 页自动跳登录 |
| 上传 | 多文件上传向导；**5MB 分块断点续传**（偏移不符自动续传）；后台上传托盘（进度/速度/重试/排队）；无 JS 回退整文件 POST；**Google Drive Picker 直拉**（机房↔Google，绕开本地上行） |
| 转录 | WhisperX 流水线：ffprobe → 视频抽轨 → 16k 合并 → 场景词库拼 prompt → 转录 + 词级对齐 + 说话人分离 → 入库；htmx 轮询自动刷新 |
| 说话人 | `channels`（按声道，离线）/ `auto` / `count`（pyannote gated）/ `off`，上传时按场景选；诊断脚本 `scripts/check_diarization.py` |
| 场景与词库 | 7 大行业预置场景 + 385 词条；词库可增删改、可建自定义库（预置受保护） |
| 搜索 | FTS5 + trigram 分词（中文子串）；bm25 排序 + snippet 高亮；按场景/公司/时间筛选；命中片段跳转高亮 |
| 整理报告 | 每场景一套整理模板（可编辑）→ Claude Code 经 MCP 生成 **HTML 报告** → 在线查看 / 导出 PDF（weasyprint）/ 下载 HTML；生成后 **Bark 通知** |
| 看板 | 首页语料总览（会议数 / 转录字数 / 音频时长 / 文件数）；会议列表整理状态列 + 筛选 + 分页 |
| 运维 | 设置页在线改运营配置（运行时覆盖 `.env`，敏感项只读打码）；SQLite 每日自动备份；`/healthz` 健康检查 |

---

## 所用技术（技术栈）

| 层 | 技术 |
|----|------|
| 语言 / 运行时 | Python 3.11（`>=3.11,<3.13`） |
| Web 框架 | FastAPI + Starlette，Uvicorn（standard） |
| 前端 | 服务端渲染 Jinja2 + Tailwind（CDN）+ htmx + 原生 JS 上传器；自定义暗色主题 CSS |
| 数据库 | SQLite + SQLAlchemy 2.0 ORM + Alembic 迁移；全文检索 **FTS5（trigram 分词器）** |
| 任务队列 | Redis + **RQ** |
| 语音转录 | **WhisperX**（Whisper large-v3）+ 词级强制对齐；**pyannote/speaker-diarization-community-1** 说话人分离；ffmpeg / ffprobe |
| GPU | PyTorch（CUDA）；NVIDIA Container Toolkit；8GB 显存优化（可配 batch + OOM 自动降批 + 阶段间释放显存） |
| 报告导出 | **weasyprint**（HTML→PDF，内嵌中文字体） |
| 智能整理 | **MCP**（FastMCP / stdio）+ Claude Code（Max 订阅） |
| 鉴权 | bcrypt + itsdangerous（签名 session） |
| 通知 | Bark |
| 外部集成 | Google Drive Picker / Drive API；HuggingFace（经 mihomo 代理直连）；frp + Nginx Proxy Manager 公网接入 |
| 配置 | Pydantic Settings；`.env` + `settings` 表运行时覆盖 |
| 部署 | Docker Compose（`app` / `worker` / `redis` / `backup-cron`） |
| 依赖 / 构建 | uv + `pyproject.toml`（hatchling） |
| 质量 | pytest（+asyncio/cov）· ruff · mypy；`tests/test_smoke.py` 覆盖导入/迁移/seed |

---

## 技术原理（架构与数据流）

### 组件拓扑

```
浏览器 ──HTTPS──> Nginx(阿里云 VPS, NPM) ──frp──> app 容器 (FastAPI :18080)
                                                     │  入队 / 读写
                                                     ▼
                                                  Redis (RQ 队列)
                                                     │
                                                     ▼
                                                  worker 容器 (GPU: WhisperX + pyannote)
                                                     │  写回 segments / speakers
                                                     ▼
                              SQLite  /data/whisper/db/whisper.db  (app 与 worker 共享)
                                                     ▲
       本机 Claude Code ──MCP(stdio, docker exec)──> app 容器内的 mcp_server
              （定时 /schedule 取待整理队列 → 生成 HTML 报告 → 写回 deliverable）

存储分层：NVMe /data/whisper（db · models · outputs）   HDD /mnt/data/whisper（recordings · inbox · backups）
```

四个服务（`docker-compose.yml`）：`app`（Web + API + 容器内 MCP server）、`worker`（GPU 转录）、`redis`（队列）、`backup-cron`（每日 DB 备份）。

### 端到端数据流

```
上传/Drive → 文件落 HDD recordings → 入 RQ 队列 → worker 转录
  → segments + speakers 入库（FTS 触发器同步）→ 详情页展示 / 全文搜索
  → 点「生成报告」入整理队列 → Claude Code 经 MCP 整理 → HTML 落盘 + deliverable
  → 详情页查看 / 导出 PDF / 下载 HTML + Bark 通知
```

### 转录流水线（`worker/jobs/process_meeting.py`）

1. **探测**：ffprobe 读时长与声道数。
2. **预处理**：视频抽音轨 → 统一重采样为 16k 单声道 WAV → 多文件按顺序合并。
3. **拼 prompt**：按会议场景关联的词库拼出 `initial_prompt`，提升专有名词识别。
4. **转录**：WhisperX（Whisper large-v3）。
5. **对齐**：词级强制对齐，得到精确时间戳。
6. **说话人分离**：按所选模式（见下）。
7. **入库**：写 `segments`（含起止时间、说话人）、`speakers`；FTS5 触发器自动同步索引。

> **8GB 显存优化**：`whisper_batch_size` 可配（本机设 4）；遇 CUDA OOM 自动降批；transcribe→align→diarize 各阶段之间释放显存（`del model; gc; empty_cache`）。

### 说话人分离原理

- `channels`：直接按音频声道拆分（双声道/每人一个麦）——**离线、不需联网模型**。
- `auto` / `count`：同声道多人，用 pyannote `community-1`（**gated** 模型）自动估计或按指定人数聚类。
- `off`：不分离。详细配置见 [说话人分离](#说话人分离-speaker-diarization)。

### 异步分块上传

`POST /meetings/draft` 建草稿 → `PUT …/chunk?offset=` 逐块（每块 5MB，远小于 nginx 体积/超时限制；偏移不符返回 409 → 自动续传）→ `POST …/finalize` 入队。`static/upload.js` 是全局上传管理器，右下角进度托盘，失败重试、可排队多场会议；导航用 htmx-boost 只换 `#page`，上传不中断。无 JS 时回退为原始整文件 POST。

### 全文搜索

`segments_fts` 用 **trigram 分词器**（替换初版 `unicode61`——它不切中文），因此中文子串可搜；bm25 排序 + snippet 高亮；触发器（`segments_ai/ad/au`）保持与转录同步；查询 <3 字时回退 LIKE。逻辑见 `app/services/search.py`、`/search` 页。

### 转录后整理（报告生成）

见下方 [转录后整理](#转录后整理报告生成-自动还是手动) 一节——这里明确「自动 vs 手动」。

### 配置与存储

- **配置覆盖**：`settings` 表在运行时覆盖 `.env`（app 与 worker 共用），设置页可在线改运营项；HF_TOKEN 等敏感项只读打码，写操作限管理员。
- **双盘分层**：NVMe 放 `db / models / outputs`（热数据、模型缓存、产出）；HDD 放 `recordings / inbox / backups`（大文件冷数据）。

---

## 操作流程

### A. 部署（首次）

前置：Docker + Docker Compose；NVIDIA Container Toolkit（GPU 模式）；≥16GB RAM、≥50GB 磁盘；一个已接受 [pyannote/community-1](https://huggingface.co/pyannote/speaker-diarization-community-1) 条款的 HuggingFace token（仅 `auto`/`count` 需要）。

```bash
# 1. 克隆
git clone git@github.com:thethirdfive/whisper-server.git
cd whisper-server

# 2. 配置环境变量
cp .env.example .env
nano .env   # 至少：APP_SECRET_KEY、ADMIN_PASSWORD_BCRYPT、HF_TOKEN

# 3. 生成 ADMIN_PASSWORD_BCRYPT
docker run --rm python:3.11 python -c \
  "import bcrypt; print(bcrypt.hashpw(b'你的密码', bcrypt.gensalt(12)).decode())"

# 4. 启动（首次会自动建表、加载场景词库、创建管理员）
docker compose up -d
docker compose logs -f app

# 5. 访问
open http://localhost:18080
```

> 需要 GPU 的 `auto`/`count` 分离与公网接入还有额外配置，见 [说话人分离](#说话人分离-speaker-diarization) 与 [公网接入](#公网接入)。

### B. 日常使用

1. **上传** — 「会议 / Meetings」→「新建」：选场景、说话人分离模式、可选自定义 prompt → 拖入文件或用 Google Drive 选择 → 后台上传（右下角托盘看进度）。
2. **转录** — 上传完成自动入队；详情页 htmx 轮询状态，完成后展示转录（含时间戳、说话人），可「导出 TXT」。
3. **检索** — 顶栏搜索框做全文搜索；命中片段点开跳转到对应会议的该段并高亮；列表/搜索均可按场景/公司/时间筛选。
4. **生成报告** — 详情页「整理报告」区点「生成报告」→ 进待整理队列；待 Claude Code 整理后，可在该区查看 / 导出 PDF / 下载 HTML，并收到 Bark 通知。**前提是已按下节配好 Claude Code 定时整理。**
5. **维护** — 见 [常用命令](#常用命令)；DB 每日自动备份到 HDD。

### C. 让 Claude Code 定期整理（一次性配置）

```bash
cd /home/ai/whisper-server && claude     # 仓库根已有 .mcp.json，首次提示批准 MCP server `whisper`
# 在 Claude Code 里 /mcp 应看到 whisper 已连接、5 个工具可用
# 用 /schedule（推荐，cron）或 /loop 30m 定期跑 docs/organize-prompt.md 的整理 prompt
```

完整说明见 [docs/organize-with-claude-code.md](docs/organize-with-claude-code.md)。

---

## 转录后整理（报告生成）：自动还是手动？

**当前是「半自动」**，分清两步：

- **入队（手动）**：每场会议需要你在详情页点「生成报告」，把它放进待整理队列（`report_status=queued`）。
- **生成（依赖 Claude Code）**：真正把转录整理成 HTML 的是你机器上的 **Claude Code 经 MCP**。它**不是常驻服务**——需要你用 `/schedule`（cron）或 `/loop` 让它定期跑整理 prompt（或手动跑一次）。**没有 Claude Code 在跑，队列里的报告不会自动生成。**
- 一旦配好 `/schedule`，体验上接近「自动」：点完「生成报告」，下个调度周期就生成并 Bark 通知。走 Claude Max 订阅，几乎零额外 API 费用。

整理器的工作循环（prompt 见 `docs/organize-prompt.md`）：

```
list_pending_reports() → 对每条 claim_report(id) → get_meeting(id)（取场景模板 + 转录全文）
  → 按模板生成自包含 HTML → submit_report(id, html, summary) → 落盘 + deliverable + 置 done + Bark
  （失败则 report_failed(id, error) 并继续下一条）
```

> **MCP server 跑在 app 容器内**（`mcp_server/server.py`，已打进 app 镜像），`.mcp.json` 用 `docker compose exec -T app python -m mcp_server.server` 以 stdio 连入。原因：SQLite 库文件由容器以 root 写入，本机用户进程直接连会报 `readonly database`；在容器内跑则库/产出目录/代理/依赖都与 app 一致。

> **完全服务端自动**（无需 Claude Code）的「方案二」——系统内置 LLM API worker（DeepSeek/Gemini），复用同一队列/模板/产出接口——**尚未实现**。

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

`pyannote/speaker-diarization-community-1` 是 **gated（受限）模型**，要用 auto/count 需满足两点：

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
# 看到 "说话人分离已就绪 ✅" 即可
```

> 实在没有可用代理 → 直接用 **按声道拆分** 模式（双声道录音完全不依赖这个模型）。

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

# 跑迁移 / 创建新迁移
docker compose exec app alembic upgrade head
docker compose exec app alembic revision --autogenerate -m "你的描述"

# 诊断说话人分离模型
docker compose exec worker python scripts/check_diarization.py

# 重置数据库（开发环境！）
docker compose down -v && rm -rf /data/whisper/db/* && docker compose up -d

# 手动触发备份
docker compose exec backup-cron /backup.sh
```

本机不重建 6GB worker 镜像快速迭代 app 层（uv venv + TestClient 跑临时 SQLite）：见
`pyproject.toml` 的 `dev` extra 与 `tests/test_smoke.py`。

---

## 项目结构

```
whisper-server/
├── app/                       # FastAPI 应用（Web + API + 容器内 MCP 由此镜像承载）
│   ├── main.py                # 入口（含 /healthz、版本号）
│   ├── config.py              # Pydantic Settings（.env + settings 表覆盖）
│   ├── database.py            # SQLAlchemy + session
│   ├── __init__.py            # __version__（版本号单一真源）
│   ├── models/                # 15 张表的 ORM
│   ├── api/                   # 路由（meetings / search / scenarios / vocab / settings…）
│   ├── auth/                  # 账密 + 签名 session
│   ├── services/              # 业务逻辑（queue / reports / search…）
│   ├── templates/             # Jinja2 模板
│   ├── static/                # CSS / 上传器 JS
│   ├── i18n/                  # 中英文翻译
│   └── ws/                    # WebSocket
├── worker/                    # RQ worker（jobs/process_meeting.py：WhisperX 流水线）
├── mcp_server/                # MCP server（server.py，stdio，整理报告 5 工具）
├── migrations/                # Alembic（001 建表 → 006 FTS trigram 等）
├── seeds/                     # 预置场景 + 385 词条
├── scripts/                   # create_admin / backup / check_diarization / setup-storage
├── docker/                    # Dockerfile.app / .worker / .backup
├── docs/                      # organize-with-claude-code.md / organize-prompt.md
├── tests/                     # test_smoke.py 等
├── docker-compose.yml         # app / worker / redis / backup-cron
├── pyproject.toml             # uv 管理依赖（含 mcp / worker / dev extra）
├── .mcp.json                  # Claude Code 的 whisper MCP server 定义
├── alembic.ini · .env.example · CHANGELOG.md · README.md
```

---

## 版本控制与变更记录

- **版本号**：遵循[语义化版本 SemVer](https://semver.org/lang/zh-CN/)。**单一真源**是 `app/__init__.py` 的
  `__version__`（页脚显示、`/healthz` 与 FastAPI `version` 都读它），与 `pyproject.toml` 的 `version`
  保持一致。`0.x` 表示 1.0 前的活跃开发期：次版本号递增=新功能，修订号=修复。
- **分支模型**：
  - `dev` — 默认/集成分支（远端 `origin/HEAD` 指向它）。
  - `main` — 稳定 / 已部署分支。
  - 功能建议走特性分支 + PR 合入。（注：历史上部分特性为节奏直接提交到 `main`，后续逐步收敛到 PR 流程。）
- **提交规范**：[Conventional Commits](https://www.conventionalcommits.org/zh-hans/)，前缀 `feat / fix / docs / refactor / chore …`，
  描述用中文并说明「为什么」。
- **变更记录**：见 [CHANGELOG.md](CHANGELOG.md)（[Keep a Changelog](https://keepachangelog.com/zh-CN/1.1.0/) 格式）。每次有用户可感知的改动时更新。
- **发布流程**：合并到 `main` → 同步 bump `app/__init__.py` 与 `pyproject.toml` 的版本 → 更新 CHANGELOG →
  打 tag `vX.Y.Z`（与 `__version__` 一致）。
- **数据与迁移**：任何表结构变更必须出 Alembic 迁移（`alembic revision --autogenerate`）；DB 每日由
  `backup-cron` 备份到 HDD。

---

## 公网接入

把家里 homeserver 经 frp 暴露到阿里云 VPS：

1. 在 homeserver 的 `frpc.toml` 追加一段，把本地 `127.0.0.1:18080` 反代到 VPS。
2. 阿里云 VPS 的 Nginx Proxy Manager 加 host `whisper.abowk.cn` → 该 frp 端口。
3. 启用 SSL（Let's Encrypt）。
4. 在 NPM 的 Advanced 里加 WebSocket 支持（转录状态需要）。

---

## 许可

Private. © 2026 Ethan.
