# G4/R4.4｜已有真实镜头接入通用短剧流水线（无费，不回生成）

**核心目的：让任何剧本/任意角色的真实视频片段接入原有 W3 渲染器，不为换场景或校验再付费。** CityDiscount 是 Pilot 01，仅证明 Google 真实参考图能跑通；本接口不存在任何 CityDiscount 路径、Woolworths 字样、12镜固定镜头顺序、独立品牌后期。

## 已有与本轮唯一新增

- 已有：`EpisodeDraft`（逐镜 shot_id/时长）、`media_ingest.inspect_source`（真实字节 SHA、ffprobe、音轨检查）、`offline_render.render_approved_preview`（已有 HTTP/SQLite 正式脚本/角色审批门禁、原真实视频片段→本地标准视频片）、W4/W5 审片。**不改这些已完成源码。**
- 新增一个纯本地、无 API 的 `admit_existing_real_shots(episode, inputs, require_full_episode=False)`，它将真实素材、供应商自报 receipt 和运营者预先固定的独立 SHA 拼成现有 `source_clips: dict[shot_id,Path]`，**不自动调用生成/重试/下载，不存媒体，不做发布**。
- 源 MP4 SHA（由操作者从已知可信媒体另行固定）必须与本地文件**和**产生时记录的 `source_video_sha256` / `source_mp4_sha256` / `video_sha256` 三者中的唯一一个相等；receipt 需真实 reference 入口自报 `model_calls=1`、`source_video_real_model=true`、`provider_reference_applied=true`、有效引用数、`publication_approved=false`。旧的 prompt-only 原始 F3 report **不会**自动伪装为真实 reference receipt。
- 若部分真实镜头尚缺，`missing_real_shot_ids` 明列，不允许 `require_full_episode=True` 通过。对完整剧本的合成，仍需由原有 `render_approved_preview` 完成本地规范化、可追踪技术视频和 Fake 对照；本接口绝不擅自补真镜头、声称全片完成或用户审片成功。
- 导出 report 不含本地路径、私人媒体、base64、API Key；只包含 shot ID、SHA、来源哈希、时长、音轨存在、费用是否已核实与未授权发布等审计字段。由于供应商 receipt 是**操作者保存的 JSON**而非供应商签名，`provider_receipts_self_reported_not_authenticated=true`；即使 sha 正确仍不声称实际法律/云账单已核实。

## 使用同一接口（两个完全不同题材）

```python
from pathlib import Path
from drama_factory.pipeline.existing_real_shots import admit_existing_real_shots
from drama_factory.pipeline.offline_render import render_approved_preview

# episode 是现有批准数据 EpisodeDraft；db/production_id 的审批流程
# 必须已通过，不能靠此函数自动批准。
sources, handoff = admit_existing_real_shots(
    episode,
    [{
        "shot_id": "s02",
        "media_path": Path("/private/approved-output/shot02.mp4"),
        "receipt_path": Path("/private/approved-output/receipt02.json"),
        "expected_sha256": "<由独立可信位置固定的真实64位SHA256>",
    }],
    require_full_episode=False,
)
# sources 保留本地 Path 给已有 renderer；handoff 可写审计报告。
# 在 production 已经过 script + character 双审批后，才可使用：
# technical = render_approved_preview(db, production_id, local_root,
#                                     source_clips=sources)
```

**绝不把示例的 SHA 占位符当可执行凭据。** 本功能不自动创建 EpisodeDraft、数据库、收费许可或完整12镜成片。

## 真实证据与局限

已有有偿运行：s02 [#39583047905](https://github.com/Mrlukahuang/ai-short-drama-factory/actions/runs/39583047905) 与 s05 [#39596195021](https://github.com/Mrlukahuang/ai-short-drama-factory/actions/runs/39596195021)，各一次 Google真实生成；s05 最后的红灯是存档路径错，已由 PR #225 合并修复，**不应再付费重跑**。它们在同一天或其他账单结算期间的 Google 实际收费仍未知。

本轮只是**工程桥梁的合成夹具合同测试**：跨两部不同题材测试相同 MP4输入/来源 SHA 和错误拒绝；CI 没有从 Google 取新视频，也没有真实 G4 片子的完整集成审片。下一步应在 Owner 独立审批通过后，让真实 W3/W4 对混合既有镜头做整片0-call技术/内容审查；不做新多镜付费生成。G4依旧 NOT_READY，G5禁止。
