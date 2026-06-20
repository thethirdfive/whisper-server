用 whisper MCP 整理待办报告：

1. 调 list_pending_reports() 取待整理会议；没有就结束。
2. 对每一条：claim_report(id) → get_meeting(id) 拿全部上下文。get_meeting 返回：
   - template_instructions：该场景的整理模板（最高优先级，按它来写）；
   - scenario / scenario_description：**场景设定**（这类会议的背景与侧重）；
   - report_context：用户为本场会议**自定义的整理要求 / 备注 / 特点 / 上下文**；
   - tags：备注标签；custom_prompt：转录提示词（含专有名词，供整理参考）；
   - transcript：带说话人/时间戳的转录全文。
3. 严格按 template_instructions 生成一份自包含的完整 HTML 文档（内联 CSS、中文、排版美观、
   善用表格/列表/层级体现要点关联；忠于转录、不杜撰）。报告**必须**：
   - 顶部体现「场景设定」（依据 scenario_description）；
   - 顶部体现「备注 / 特殊强调」（综合 report_context 与 tags），并据此在正文取舍详略，
     用户特别要求的点要重点展开；
   - 剔除明显的混录噪声（如反复出现的「请点赞订阅转发打赏」等视频噪声、与议题无关的来电对话）。
4. submit_report(id, html=<完整HTML>, summary=<一句话摘要>)。
5. 任何一条失败就 report_failed(id, error) 并继续下一条。
6. 全部处理完，简要汇报：成功 N 条、失败 M 条（及失败原因）。
