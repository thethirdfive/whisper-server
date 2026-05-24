# 转录后整理（方案一：Claude Code + MCP）

录音转写完成后，把会议整理成一份**HTML 报告**。整理由你服务器上的 **Claude Code** 经 **MCP**
驱动——走 Max 订阅，几乎零额外费用。

## 架构

```
Whisper 系统  ──(MCP, stdio)──  Claude Code (本机, 定时跑)
   │  list_pending_reports()   待整理队列(report_status=queued)
   │  get_meeting(id)          元数据 + 场景整理模板 + 转录全文
   │  claim_report(id)         标记 processing
   │  submit_report(id, html)  回收 HTML → 落盘 + deliverable + done + Bark 通知
   └  report_failed(id, err)
```

- MCP server：`mcp_server/server.py`，stdio 直连系统同一个 SQLite（`/data/whisper/db/whisper.db`）。
- 报告产出：HTML 存到 `/data/whisper/outputs/{meeting_id}/`，并在会议详情页「整理报告」区可查看/下载。
- 通知：生成后发 Bark（需在设置/`.env` 配 `BARK_KEY`，没配则跳过）。
- 模板：每个场景一套（场景页「整理模板」可编辑），没配就用内置默认。

## 一次性准备

1. 建 MCP 专用 venv（已含 app 依赖 + mcp）：
   ```bash
   cd /home/ai/whisper-server
   uv venv .venv-mcp && VIRTUAL_ENV=.venv-mcp uv pip install -e ".[mcp]"
   ```
2. 仓库根已有 `.mcp.json`，Claude Code 在本目录启动时会自动发现 `whisper` 这个 MCP server。
   验证：在本目录跑 `claude`，输入 `/mcp` 应能看到 `whisper` 已连接、5 个工具可用。

## 让它定期整理

在系统里：会议转录完成 → 详情页点「生成报告」→ 进入待整理队列。

让 Claude Code 定期处理队列，二选一：

- **定时（推荐）**：用 `/schedule`（cron routine）每隔一段（如 30 分钟）跑下面的 prompt。
- **轮询**：用 `/loop 30m` 跑下面的 prompt。

整理 prompt（`docs/organize-prompt.md` 也存了一份）：

```
用 whisper MCP 整理待办报告：
1. 调 list_pending_reports() 取待整理会议；没有就结束。
2. 对每一条：claim_report(id) → get_meeting(id) 拿 template_instructions 和 transcript。
3. 严格按 template_instructions 生成一份自包含的完整 HTML 文档（内联 CSS、中文、排版美观、
   善用表格/列表/层级体现要点关联；忠于转录、不杜撰）。
4. submit_report(id, html=<完整HTML>, summary=<一句话摘要>)。
5. 任何一条失败就 report_failed(id, error) 并继续下一条。
```

## 方案二（以后）

同一套队列/模板/产出接口，换成系统内的 LLM API worker（DeepSeek/Gemini）即可，更快但按量计费。
