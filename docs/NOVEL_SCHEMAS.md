# 小说改编域 Schema v1

在 `src/drama_factory/novels/contracts.py` 中实现纯结构化模型，不执行模型、章节抽取或付费生成：

- `NovelSource`：小说 ID、上传源文件 SHA-256 和章节数，必须匹配数据库中的原始记录。
- `SourceSpan`：原文的绝对字符偏移范围及章节序号，校验时不允许跨章节边界。
- `CharacterMention`：原文人物提及与对应来源定位，不等于已经批准的虚拟演员 ID。
- `PlotEvent`：情节事实、来源、参与人物、剧中顺序与因果关系。
- `SeasonPlan` / `SeasonEpisodePlan`：改编集数、时长、对应事件和每集首尾钩子。
- `NovelAdaptationBlueprint`：验证全部引用一致、前置因果、章节归属、集数连续。

此 Blueprint **不能证明已获改编权**，只是校验输入结构。已上传但版权状态为 `pending` 的原文仍不得发送给外部模型。PR-05 将实现基于章节的本地节选与事件任务准备、引用与缓存；PR-06 实现更细粒度的人工权益许可审批。

设计遵循最小化保存原则：不在每个事件/人物 JSON 中冗余复制小说原文，事件记录只包含文本摘要和 SourceSpan 引用。外部 AI 调用、长文本分析、续跑、映射到指定剧集由后续单独实现并经过版权与用户许可检查。
