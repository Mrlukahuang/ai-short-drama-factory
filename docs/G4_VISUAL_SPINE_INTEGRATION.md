# G4 基础生产框架 FND-02/03：多视图 → 参考媒体 → 首尾帧 → Omni Fake 集成

**Stage:** G4 · **Req:** R4.4 · **架构输入:** [#181](https://github.com/Mrlukahuang/ai-short-drama-factory/issues/181)、[FND-02 #185](https://github.com/Mrlukahuang/ai-short-drama-factory/issues/185) 和 `docs/G4_VISUAL_PRODUCTION_ARCHITECTURE.md`。主线仍 **G4 NOT_READY**。本功能**不**授权模型消费真实人像或著作权图片、收费视频生成、任何发布或 G5/W6。

## 为什么改框架，而不是继续修12镜

旧视频流程只把人物 appearance/服装/道具描述**重复附加到每镜文字 Prompt**。历史 `providers/google_omni_video.py` 是 `input=spec.prompt`，主动拒绝 `reference_images`；已有 `pipeline/shot_asset_binding.py` 虽记录规格 JSON SHA 与角色、场景版本，却不代表参考图已传给视频模型。12镜反复出现眼睛/发型/服装/杯子/桌面/风格漂移是这种生产控制缺失的重要实证，但某一种具体模型对多图有多大改善仍**未经真实付费 A/B 验证**。

**参考的成熟框架（不照搬平台）：** [ViMax@fd4b72e](https://github.com/HKUDS/ViMax/tree/fd4b72e7731be6e5f88486206d25ea59849b0285) 的 portrait generator/camera tree/reference-image selector/best-image selector（MIT）；[Jellyfish@a967819](https://github.com/Forget-C/Jellyfish/tree/a9678194ddf2d9be3ccbe78d4287d87d5089e123) 的 shot assets/first-last-key video readiness（Apache-2.0）。Huobao 的 @角色/@场景/@道具仅借设计（CC BY-NC-SA）；OpenMontage/ArcReel 的 AGPL、waoowaoo 的 Elastic 只借架构思想。当前 PR **没有复制这些第三方源代码**。

## 真实文件级 Production Spine

| 顺序 | 使用模块 | 输入 → 输出 | 状态 |
|---|---|---|---|
| 1 | 原有 W2 `shot_asset_binding.py` | 已审批剧本、actor/scene/voice ID 与 version/specification SHA → 固定 12 镜 manifest | 保持原样、只读 |
| 2 | FND-01 `visual_production_plan.py` | actor 正侧背图、固定场景/道具与 shot dependencies → 逐镜有序 references、计划 SHA | 已合并、只离线 |
| 3 | FND-03 **新** `visual_keyframe_graph.py` | 已由真人检查的 first/last 图片元信息，显式同场景 shot dependency → 本镜 first/last 或上一镜 last 继承、缺图阻断 | 已编码；人工 metadata 不是独立图片权限 |
| 4 | FND-02 **新** `visual_media_admission.py` | 图片 PNG 真实字节/SHA/有效 RGB/尺寸，操作员签名版本与逐镜 grant → 可信 *本地*媒体 bytes/角色序列 | 独立HMAC只是审批声明完整性，并非法律产权证明 |
| 5 | FND-02 **新** `omni_media_envelope.py` | 1–8 条*本地配置上限*的媒体与 fixed shot prompt → Gemini Omni Interactions `input` 中 `image + text` 及 IMAGE_REF_0 / FIRST_FRAME / LAST_FRAME、无私密内容 receipt | **仅内存 dry-run**，不提交给 Google |
| 6 | FND-02/03 **新** `visual_spine_offline.py` / CLI | 12 镜 JSON、operator grants、PNG 路径、可选 keyframe → 12 个 Fake 请求 receipt 与整集稳定 SHA | USD0、网络0、真实视频0 |
| 7 | 原有 W3/W4/W5 | MP4/AAC+字幕 → 内容 QA 与 G4 验收 | 保持原样；内容与发布仍不通过 |

**严格不变式：** `provider_reference_applied=false`、`model_submission_allowed=false`、`production_assets_verified=false`（如原 W2）、`new_paid_model_calls=0`、`actual_fee_usd=null`，直到经另一条独立的**真实**媒体上传/Provider 审计路径实证。**Fake 的 Base64 请求与多媒体标签格式正确，不等于模型已消费媒体。**

## 运行12镜离线端到端验证

零模型调用，命令只是读取**已有**本机获准的合成测试 PNG，输出 sanitized JSON。需要由独立人工授权流程签发的 `g4-visual-media-operator-grant.v1`；CLI 本身绝不签发许可，也绝不读取 API Key：

```bash
# 仅在执行人已评估真实使用权、保密、供应商可接受性后：
export DRAMA_VISUAL_OPERATOR_HMAC_KEY_HEX="<operator-secret-hex-at-least-32-bytes>"
python scripts/g4_visual_spine_offline.py \
  --w2-manifest /secure/w2.json \
  --shot-specs /secure/shot_specs.json \
  --gallery /secure/gallery.json \
  --prompts /secure/prompts.json \
  --image-index /secure/png_sha_to_file.json \
  --operator-grants /secure/explicit_operator_grants.json \
  --approved-frames /secure/reviewed_first_last_frames.json \
  --require-first-frame \
  --out /secure/new-offline-replay-receipt.json
```

输入结构及合法可重复的示例见 `tests/test_g4_visual_spine_full.py` 的合成资产 12-shot integration。**注意**：`gallery` 中旧 FND-01 的 `rights_independently_verified=true` 是测试元数据，只是声明；现有 `local_asset_references.py` 的真实存档严格为 `rights_independently_verified=false` 且 `shot_reference_board.py` 标记 `model_use_approved=false`，因此不能用本命令自动授权它们。申请外部模型上传前需先完成真实权利与保留政策确认、独立授予操作员签名，不得拷贝测试密钥。受控样例中操作员必须显式调用 `issue_operator_grant(...)` 并对每次修改/到期重新批准；**不得将该函数放在无人值守的 worker**。

运行前不向外上传图片，成功输出仅有请求指纹和角色/资产 SHA，不含 base64 字节、路径或 HMAC key；输出路径已存在一律拒绝覆盖。网络有任何需要即不是本任务允许范围。

## 官方 Omni 模式、Provider 硬边界

[Google 官方 Gemini Omni 文档](https://ai.google.dev/gemini-api/docs/omni) 说明 `gemini-omni-1.1-flash` 支持 Interactions API 多模态 `input`、`<IMAGE_REF_N>`、`<FIRST_FRAME>` / `<LAST_FRAME>`，并有 `video_config.task=reference_to_video` 等模式。**该项目当前仍不改动现有 Omni live adapter**，因其 prompt-only，尚缺**实际权限+用户授权+供应商 API 版本/入参大小/数量实测/真实费用 receipt**。本模块选取8张作为本地安全策略，不宣称供应商保证8张的同脸约束；真实服务限制须单独核查。360p 费用估算不等于硬上限，早期一次 USD5 认可不能复用。

未来 FND-04（**未获执行授权**）必须通过单独 issue/PR：
1. 验证当前 SDK 的真实多媒体提交路径与 Google 具体模型接受的输入/数量/费用范围，明示远端保留及权利情况；
2. 使用同剧本、同角色、同场景/杯桌素材的2–3镜头，与原 prompt-only 做盲评；逐次保存 request SHA/Provider ID/实际账单；
3. 经过人工验证同脸、服装、杯子/桌面、分镜连续性确有改善后，再考虑旧12镜批次级重生成；
4. 中文对白仍走独立的 speaker/actual ASR/人工听审通道，不能从三视图推断解决。

## 测试/交付纪律

`pytest -q tests/test_g4_visual_production_plan.py tests/test_g4_visual_spine_full.py`；必须执行 GitHub 全量6项 scope、Python3.11/3.13、offline-video、Fake episode、libSQL，**全绿且固定 HEAD 后**可按 AMEND-004 自治合并。

每次失败依赖现有单镜命中集合：修改 `s02` 仅把其显式依赖后代失效；源 MP4 的历史 SHA、W1–W5 旧合同不能修改；未获真实人审、Provider API receipt、版权/预算/发布批准，G4 一直 `NOT_READY`。当前 `AMEND-006` 原“暂不需要定妆照”历史决定须 Owner 正式复核后才能把参考图改为生产默认。
