# PR-05 小说章节级分析任务准备

此阶段只实现**本地离线分块清单**，尚无事件抽取模型。系统在版权字段通过初步门槛后读取本机提取文本、按照现有章节绝对偏移及 4000 字符大小切分；任何章节既不丢失字符也不重叠。

- `POST /api/v1/novels/{source_id}/analysis/prepare`：计算并缓存可恢复的 chunk 元数据。
- `GET /api/v1/novels/{source_id}/analysis/chunks`：返回章节、偏移、哈希及 pending 状态，不返回原文。
- Chunk ID 稳定、相同任务 `INSERT OR IGNORE`，重复发起不会重复创建工作项。
- 表 `novel_analysis_chunks` 为未来 Worker 状态、失败重试和事件提取保留空间。
- 版权状态 pending 或未明确申明 screen_adaptation 时拒绝任务准备，上传章节索引功能不受影响。

**边界：**仅记录候选任务，`extraction_started=false`、`model_calls=0`、`source_text_sent_to_provider=false`。并非真正“AI 情节抽取”或续跑引擎。下一阶段再引入 Worker、事件 JSON 缓存、错误/退避重试；开始第三方模型分析前仍需更完整的版权与费用审批。
