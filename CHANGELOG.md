# 变更记录 / Changelog

本项目所有重要变更记录于此。格式遵循 [Keep a Changelog](https://keepachangelog.com/zh-CN/1.1.0/)，
版本遵循[语义化版本 SemVer](https://semver.org/lang/zh-CN/)。版本号单一真源为 `app/__init__.py` 的 `__version__`。

## [未发布 / Unreleased]

### 优化
- 会议详情页：把「整理报告」区块上移到转录文本之上，生成/查看/导出 PDF/下载 HTML 等操作无需下滑即可点到。

### 文档
- 重写 `README.md`：补全**所用技术 / 技术原理（架构与数据流）/ 操作流程 / 版本控制**四大块，
  明确报告生成为「半自动」（入队手动 + Claude Code 经 MCP 定时整理），修正过时的进度/项目结构/失效链接。
- 新增本 `CHANGELOG.md`。

---

## [0.1.0] - 2026-05-24

首个可用的内部版本：从录音到「可检索 + 可整理成报告」的完整闭环。

### 新增 — 基础设施
- 项目骨架、`docker-compose.yml` + 三个 Dockerfile、`.env.example`、uv/pyproject 依赖管理。
- 15 张表的 SQLAlchemy ORM；Alembic 迁移（001 建表 → 002 词库 seed）；首启自动建表/加载场景词库/创建管理员。
- 账号密码登录（bcrypt + 服务端签名 session）；`/healthz`；SQLite 每日备份；未登录自动跳登录页。

### 新增 — 核心功能
- **WhisperX 转录流水线**（`worker/jobs/process_meeting.py`）：ffprobe → 视频抽轨 → 16k 合并 →
  场景词库拼 prompt → 转录 + 词级对齐 + 说话人分离 → 入库；htmx 状态轮询自动刷新。
- **说话人分离 4 模式**（migration 003）：`channels`（离线，按声道）/ `auto` / `count`（pyannote gated）/ `off`；
  诊断脚本 `scripts/check_diarization.py`；worker 经本机代理直连 huggingface.co 取 gated 模型。
- 词库管理 UI（增删改、自定义库、预置受保护）；上传向导（多文件、场景、自定义 prompt）；
  会议列表/详情页；场景浏览页；设置/系统信息页。
- **大文件分块断点续传**（5MB/块，draft→chunk→finalize，409 自动续传）+ 后台上传托盘（进度/速度/重试/排队）；无 JS 回退整文件 POST。
- **Google Drive Picker 直拉**：服务端用短期 token 从 Drive 直接下载（绕开本地上行）→ 入队。
- **全文搜索**（migration 006）：FTS5 + trigram 分词器（中文子串可搜），bm25 + snippet 高亮，触发器同步，<3 字 LIKE 兜底。
- **转录后整理（方案一）**：每场景一套整理模板（migration 005，可编辑）→ Claude Code 经 **MCP**
  （`mcp_server/server.py`，5 工具，跑在 app 容器内）生成 **HTML 报告**；详情页查看 / 导出 PDF（weasyprint）/ 下载 HTML；Bark 通知。
- 首页语料总览（会议数 / 转录字数 / 音频时长 / 文件数）；会议列表整理状态列 + 场景/公司/时间筛选 + 分页；
  搜索筛选 + 命中片段跳转高亮（`#seg-{id}`）。

### 体验
- 视觉改版：深空暗色 · 青蓝霓虹主题 + 波形 Logo（`static/style.css` 统一覆盖 Tailwind，全站一次性变暗）。

### 修复
- 8GB 显存 CUDA OOM：`whisper_batch_size` 可配 + OOM 自动降批 + 阶段间释放显存。
- `.gitignore` 的 `models/` 误伤 ORM 包；`.env` bcrypt 含 `$` 被 compose 插值损坏；
  `BACKUP_CRON_SCHEDULE` 未加引号致 `source .env` 报错；RQ 2.x 移除 `Connection`；Starlette 新版 `TemplateResponse` 签名。
- MCP server 改为在 app 容器内运行（解决本机进程写 SQLite 的 `readonly database`）；强制日志走 stderr，避免污染 stdio JSON-RPC。

[未发布 / Unreleased]: https://github.com/thethirdfive/whisper-server/compare/main...dev
[0.1.0]: https://github.com/thethirdfive/whisper-server/releases/tag/v0.1.0
