# G4/R4.1 中文编剧比较（离线准备，2026-10-17）

状态：PLAN ONLY；不是正式模型选型或付费授权。关联 Issue #146。
所有者已同意继续准备。正式 R4.1 尚未完成；STAGES 的 Claude 文字仍待所有者批准调整。

## 固定首轮

3 个原创题目（误会喜剧、伏笔反转、道具接续）× 3 个候选 × 2 次独立生成，共18份。
候选：gpt-6.1-sol（质量基线）、gpt-6-luna、gemini-3.8-flash；显式 medium。
这不是已证明的质量排名；各厂商 medium 不等于同一计算量。
每题复用完全相同的 fixture Bible、资产 ID、60秒目标和 R4.2 Prompt。
这里的资产是隔离测试 ID，没有写入生产数据库，也不是已批准的生产演员。
首次不生成视频，不测两段式，不扩建状态系统；选出候选后再比较思考强度。

## 已交付的离线命令

```bash
PYTHONPATH=src python scripts/prepare_writer_comparison.py --out /tmp/writer-packet.json
PYTHONPATH=src python scripts/prepare_writer_comparison.py \
  --candidate-json /tmp/candidate.json --case misunderstanding --out /tmp/check.json
```

第一条生成18个待授权任务、三个公共Prompt及哈希、现有Screenplay JSON Schema。
第二条只读本地候选JSON并校验；失败退出1，成功也不审批。
输出只创建、不覆盖。没有 SDK 调用或网络路径，没有真实文本 Provider。
导出的Schema为仓库原始schema，尚未完成供应商strict schema适配或端点验收。
现有 TextProvider 返回 ScriptOutline，而新Prompt要求 Screenplay；
后续真实接入需要显式对齐契约，不能假装换个模型字符串即完成。

## 评分与揭盲

执行者保管 model/case/replicate 与随机样本编号的映射；评分者只看统一格式的剧本。
同题打乱顺序，不展示模型、耗时、费用、思考说明；评分封存后再揭盲。
不删除失败稿、不挑最好稿。首轮不自动修复；首次失败单独计入。
若之后做一次定向修复，保留前后稿和全部费用，另报修复后通过率。
人工编辑均衡分配，记录实际操作分钟和改动类型；单人评分也必须明确标为单人。
LLM评审仅找问题，不能作为最终质量裁决或自动批准。

| 人工项 | 分数 |
|---|---|
| 前8秒钩子 | 1–5 |
| 冲突与因果、反转铺垫 | 1–5 |
| 中文对白与人物区别 | 1–5 |
| 镜头可制作性 | 1–5 |
| 道具、服装、轴线和起止接续 | 1–5 |
| 结尾悬念 | 1–5 |

可用稿暂定标准：结构检查全过、无严重语义连续性错误、各人工项≥3、
人工能在10分钟内修到愿意拍摄。所有者可以在生成前调整阈值；生成后不追改标准。
分别报告质量、首次结构通过率、人工分钟数、每份批准稿总成本。
18份是探索性筛选，结果接近则追加新题，不宣称统计冠军。

Python复用Screenplay验证总时长、唯一镜头、说话人与出场角色、对白时槽；
另检查fixture身份/场景/演员白名单、非空钩子/悬念/连续性、3–10秒单镜。
自然语言continuity_start/end不能可靠自动判定杯子换手或轴线正确，脚本明确标记not_assessed。
复杂动作≤6秒、口语自然、对白能否实际念完均需人工检查。
结构通过不等于编剧合格、生产资产有效、视频可执行或获批发布。

## 收费执行前的待决事项

- Issue #146：确认这18份文本试验的API使用范围、OpenAI凭据和Google文本权限。
- 提议总硬上限US$2（含失败与思考token），不是本脚本已实施的扣费限制。
- 真实执行脚本须先按端点限制设置输入/最大计费输出预算并预留最坏费用；
  无法证明总上限则不调用。不自动重试，不因超时不明状态立即重发。
- 不把ChatGPT订阅当API余额；不用F3已消费的一次性授权。
- 修改治理文件需所有者批准；本次只做离线比较准备，不改正式默认模型。
- 完成文本盲评后再决定主备；视频废片节省需要后续制作实测，不能从文本分数推定。

## 资料核查入口

以下为核查入口，不作为中文短剧质量排名：
- https://developers.openai.com/api/docs/models/gpt-6.1-sol
- https://developers.openai.com/api/docs/models/gpt-6-luna
- https://ai.google.dev/gemini-api/docs/models/gemini-3.8-flash
- https://ai.google.dev/gemini-api/docs/thinking
- https://ai.google.dev/gemini-api/docs/pricing

本次复用仓库R4.2 Prompt与Screenplay，没有复制外部项目源码。

