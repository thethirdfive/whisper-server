用 whisper MCP 整理待办报告：

1. 调 list_pending_reports() 取待整理会议；没有就结束。
2. 对每一条：claim_report(id) → get_meeting(id) 拿 template_instructions 和 transcript。
3. 严格按 template_instructions 生成一份自包含的完整 HTML 文档（内联 CSS、中文、排版美观、
   善用表格/列表/层级体现要点关联；忠于转录、不杜撰；剔除明显的混录噪声，如反复出现的
   "请点赞订阅"等视频噪声）。
4. submit_report(id, html=<完整HTML>, summary=<一句话摘要>)。
5. 任何一条失败就 report_failed(id, error) 并继续下一条。
