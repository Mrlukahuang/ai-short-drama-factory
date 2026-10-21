# G4/R4.4 通用“已有真实镜头 → 本地成片 → 技术审片”一命令（零新增付费）

**用途**：复用 #226/#227 的通用真实 MP4 SHA/receipt 入库契约及仓库原有 `offline_render.render_approved_preview` 和 `offline_review.load_local_offline_review`。CityDiscount 只是 Pilot 01；命令没有品牌专有代码。已有 W1–W5、通用 Worker、SQLite schema、Provider、ASR/TTS 和审批状态机不修改。

**限制**：这不是“梗概 → 调用模型 → 完整真正短剧”一键自动收费流程，也不是发布器。只在操作者的已有本地数据库、批准剧本和现存实片上产生无费**技术预览**；不能偷偷填充缺镜头而宣称全真，不得推断人审、版权、配音质量或 G4 KPI 通过。

## 本地清单格式

操作者从下载且校验过的原始视频和来源 receipt 生成本地文件 `sources.json`：

```json
{
  "schema": "g4-existing-real-shot-inputs.v1",
  "shots": [
    {
      "shot_id": "s01",
      "media_path": "clips/s01.mp4",
      "receipt_path": "receipts/s01.json",
      "expected_sha256": "由独立来源核对的真实64位小写SHA256"
    }
  ]
}
```

此处 SHA 是格式示例，非有效凭据；实际运行前必须换成真的64位哈希。所有相对文件路径以清单所在目录为起点。只接受本地 regular `.mp4`、大小受限 JSON receipt 和输入源 SHA；拒绝 symlink、重复/外部镜头、伪造 reference 状态、错误哈希、缺审批与超时长。

## 一次命令运行

```bash
python scripts/run_g4_existing_episode_offline.py \
  --database /trusted/local/factory.sqlite3 \
  --series-id proj_1234567890abcd \
  --production-id run_1234567890abcd \
  --shot-manifest /trusted/local/sources.json \
  --output-root /trusted/local/g4-review
```

要求数据库中已存在此 Production，并由**原 API 实际完成剧本和角色两道审批**；默认 `require_full_episode=True`：一个真实镜头都不能缺。保留现有 12 镜以内、90秒以内的技术预览限制。绝不创立新 Production、新片单或 API 授权。

仅供**内部**未完成片技术观察，才可显式添加 `--allow-placeholders`：输出的 MP4 有原有 W3 占位卡，report 同时包含 `missing_real_shot_ids` 和 `has_placeholder_shots=true`，绝不声称内容齐备。**不可将占位片用于 G4 通过或发布判断**。

**输出**：沿用原有路径 `{output-root}/{series-id}/{production-id}/preview.mp4`，内部技术 `manifest.json` 与字幕；另有不含输入文件路径及内容的 `g4-existing-real-episode-replay.json`。真实 W3 FFmpeg 及 W4 二次解码复查后才提交此结果；全真素材齐全仍 `human_content_review_status=not_run`、`prior_real_provider_invoices_verified=false`、`release_status=blocked`、`publish_approved=false`，新增 Google 请求永远0。

**请勿对正式生产数据库未经备份/审查直接执行**：原有 `Database` 初始化与 `render_approved_preview` 可以写入本地 SQLite 的技术预览状态，这是现有系统行为，不是只读扫描。首先在**副本/测试数据库**及私有本地目录试运行，检查预览无误后再由操作者选择正式执行。

## 验收与后续

新 `tests/test_g4_existing_episode_offline_cli.py` 用**合成**视频+供测试的“供应商成功”声明，实际走同一 FastAPI/SQLite审批、真实 FFmpeg H264/AAC/mov_text、W4 technical QA、重复运行缓存及源 SHA 损坏拒绝。GitHub CI `offline-video` 必须真实执行并且零 skip；其他 Python 环境没 FFmpeg 的 `skip` 不得当作通过证据。

今后 Owner 的真正整集 G4 退出需要：至少6镜独立真人判可用、中文音轨内容与字幕审查、供应商**实账**与人工耗时、素材/商标完整授权、R4.3 的单独验收以及 Owner 明确批准。以上均不由本命令自动推断或授权。G4 NOT_READY，G5 不启动。
