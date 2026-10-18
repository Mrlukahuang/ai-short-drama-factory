# G4/R4.4 — W1 单镜定向修复：离线/Fake 受控闭环

> 2026-10-19 NZT；只用于**复用原始12镜真实素材做无新模型调用的验收**。不能把用已有 s04 填 s07 的模拟结果称为“质量已修好”。外部参考：Development Bible W1；OpenMontage `@c8066452325cb57c8fc1ba8c2a71b6e8842e6b65` 的 checkpoint/approval **design-only**，没有移植其 AGPL-3.0 代码。ViMax/Jellyfish/HyperFrames 源码也**未复制**。

## 现有模块与最小新增映射

| 阶段 | 复用（不重做） | W1 薄适配 |
|---|---|---|
| Script/shot | `run_gpt_video_three.load_plan(shot_ids=[...])`、原 Sol 校验 | 生成单一 `repair-plan`，附剧本、Prompt、原片及审核版本 SHA |
| 源素材/费用 | `assemble_gpt_video_three.probe/sha`、原 `report.json` | 独立费用字段 **pending**；已用 USD5 **不得复用** |
| 收片 | 旧已有 MP4（Fake 输入） | 仅标 `operator_existing_media_offline_simulation`，不冒称 provider task |
| 局部替换 | `repair_gpt_episode_offline.replace_completed_shot` | 为被替换镜头保留先前费用/任务/Prompt 收据历史 |
| 后期/QA | `postprocess_gpt_episode_offline.render_draft_postprocess` | 新版独立目录；11 镜 SHA 比对、原音轨、SRT草稿、最终MP4、后期 QA |

正式生产权威仍在 Python；**没有新数据库、Worker、模型 Provider、付费 Actions 或 UI**。

## 从已有原片执行（无收费）

先准备一份本地人工审片声明，例如 s07；`source_video_sha256` 必须从被验真的 `episode/report.json` 中读取，不得自行填写一个猜测哈希：

```json
{
  "shot_id": "s07",
  "decision": "needs_repair",
  "reason": "画面出现非预期三格分屏",
  "reviewed_by": "2026-10-19-human-review",
  "source_video_sha256": "<exact original s07 SHA256>"
}
```

然后复用真正下载的 Writer/12镜 Artifact：

```bash
python scripts/w1_single_shot_repair.py prepare \
  --writer-dir /path/to/writer-artifact \
  --episode-dir /path/to/12shot/episode \
  --delivery-dir /path/to/12shot/delivery \
  --review-file /path/to/s07-review.json \
  --output-plan /path/to/new-s07-plan.json

python scripts/w1_single_shot_repair.py fake-apply \
  --writer-dir /path/to/writer-artifact \
  --episode-dir /path/to/12shot/episode \
  --delivery-dir /path/to/12shot/delivery \
  --review-file /path/to/s07-review.json \
  --plan-file /path/to/new-s07-plan.json \
  --replacement /path/to/already-existing-compatible.mp4 \
  --output-dir /path/to/new-unallocated-W1-output
```

`prepare` 只生成版本绑定、**收费未批准**的单镜计划，不提交请求。`fake-apply` 强制对照计划所有字段、完整旧 report/交付物和已审的 `s07` 原 SHA；错误ID、旧审片、改计划、旧授权字符串、缺失/损坏素材、已存在输出路径皆拒绝。调用已有 12 镜修复后跑新的 06–10 阶段，产生：

```
<new-output>/
  w1-result.json                   # 版本、来源、费用、新旧每镜 SHA、技术/内容/发布状态
  repair/episode/report.json       # 12镜有序，11镜未动，旧receipt在offline_replacements历史
  repair/episode/s01.mp4 ... s12.mp4
  repair/delivery/                 # 合成的新父版本 MP4/delivery.json
  post/draft-captions.srt          # 剧本推定，不是ASR
  post/gpt-episode-caption-draft.mp4
  post/06_dialogue.json ... 10_qa.json
```

## 费用/授权界线

- `finance.output_estimate_plus_reserves_usd` 为**旧假设的单镜情景估算**，不能当真实供应商硬费用上限，也不能当已发票。
- `finance.independent_paid_approval=null`、`paid_execution_authorized=false`，无任何 `--paid` 入口；单次 USD5 特批已消费。`new_paid_model_calls=0`。
- 未来真正“付费生成单镜”**须单独核实**：供应商是否支持硬金额/输出时长止损；对应唯一 plan SHA + shot ID 的全新授权出处、当日支出、单次预算、一次性 claim、新任务收据以及失败不重试语义。未达任一条件前只允许本离线版本；不能悄悄解锁调用。
- 技术 QA 通过不代表新媒体人物/音色/中文对白/实际字幕正确，`publish_approved` 始终 false；旧片/旧账单文件不可覆盖。

## 验收证据与下一工作包输入

- 单测：`tests/test_gpt_w1_single_shot_closed_loop.py`，真实 FFmpeg 合成的12镜、成功回填+后期、无费用、拒绝各种失效输入。
- 主干自动离线视频复演：现有 `gpt-episode-postprocess-offline.yml` 从 **Run39130058487** 真12镜和 **Run39035812309** 原Writer下载内容，**只拿已有 s04 模拟 s07 新片**；Artifact 名包含 `W1-FAKE`。这是接口验证，**不是实际修好 s07**。
- **交接 W2 的输入**：冻结 `repair-plan` 与 `w1-result.json` 契约，shot_id、原 SHA、source_response_sha、原/新 Prompt SHA、11镜 SHA、旧 receipt、原 parent MP4 SHA、内容/发布仍未验的状态。
- **交接 W2 的输出**：每镜唯一角色/场景/speaker ID、不可变定妆锚点/资产版本和 prompt hash 对照，可消费于 W1 未来独立 paid 入口；Omni 真实参考图/音频能力目前不能冒称已支持。
- **W2 验收**：身份/资产/说话者冲突和丢版本时离线 fail-closed；同剧本计划可重复得同哈希；不更动已经生成的历史媒体。
- **W2 禁止重复开发**：不得重做 `w1_single_shot_repair.py`、`repair_gpt_episode_offline.py`、`postprocess_gpt_episode_offline.py`、`assemble_gpt_video_three.py`；不得重新造 SQLite/Worker/FFmpeg/完整 Fake 流水线，也不得动冻结 TTS 或收费。
