# G4 / R4.4 / W5 综合验收 — NOT_READY (2026-10-19 NZT)

> **阶段未退出。** 此报告为 Issue [#179](https://github.com/Mrlukahuang/ai-short-drama-factory/issues/179) 的零费用、可追溯审计。不是 G4/发布批准，也不是 W1–W4 功能重复开发。机器清单见 [G4_ACCEPTANCE_20261019.json](G4_ACCEPTANCE_20261019.json)。

## 基线与权威约束
- 重新核验 `main@2cc91f54a030ba2bc1e7e679c3f409126e912ee8`（开工时），`AMEND.md`、`AGENTS.md`、`docs/handoff/CURRENT.md`、`docs/STAGES.md`、`docs/GUARDRAILS.md`、`docs/CHARTER.md`、Development Bible / STAGE_DELIVERABLES / MODEL_HANDOFF 及 Issue #179/#177。当前 **G4 / R4.4 / W5**；`publish_approved=false`、`g4_exited=false`、G5 禁止。
- W1 [#166](https://github.com/Mrlukahuang/ai-short-drama-factory/pull/166)/[#167](https://github.com/Mrlukahuang/ai-short-drama-factory/pull/167)/[#168](https://github.com/Mrlukahuang/ai-short-drama-factory/pull/168)：离线单镜 Fake 旧 s04 替代 s07，其他 11 镜 SHA 不变；Run [39137352545](https://github.com/Mrlukahuang/ai-short-drama-factory/actions/runs/39137352545)。已交付 [W1 证据](W1_EVIDENCE_20261019.md)；真实收费单镜执行 **not_run**。
- W2 [#170](https://github.com/Mrlukahuang/ai-short-drama-factory/pull/170)：离线确定性角色/场景/服装/speaker ID、版本及 Prompt SHA，7项检查成功、Python 3.11/3.13 各883 passed/171 skipped；[标准 handoff（Issue #169）](https://github.com/Mrlukahuang/ai-short-drama-factory/issues/169#issuecomment-6251556462)。生产资产 manifest SHA **null**；reference_image/audio 没有接入。
- W3 [#173](https://github.com/Mrlukahuang/ai-short-drama-factory/pull/173)/[#174](https://github.com/Mrlukahuang/ai-short-drama-factory/pull/174)：Run [39141517448](https://github.com/Mrlukahuang/ai-short-drama-factory/actions/runs/39141517448)，真实原/FAKE 后期技术媒体，6/6 CI；[证据](W3_EVIDENCE_20261019.md)。原生 AAC 和 H264 stream copy，16 条 **DRAFT 剧本推算字幕**，未 ASR/授权配乐。
- W4 [#176](https://github.com/Mrlukahuang/ai-short-drama-factory/pull/176)/[#178](https://github.com/Mrlukahuang/ai-short-drama-factory/pull/178)：6/6 CI、Python 3.11/3.13 各897 passed/176 skipped；[证据](W4_EVIDENCE_20261019.md)；内容审查 contract 已交付。原先 **CLI 未直接跑真实 W3 两版**；下节由 W5 补足。Issue [#177](https://github.com/Mrlukahuang/ai-short-drama-factory/issues/177) 仍未批准任何新的模型调用。
- 两片共同的 writer response SHA `c5665e198eb3d30110a0bb6dc30d5f2cfadf74979eb5e6e0596d64751ff1a6f9`；原始 12 镜 report `959c3775f7846ae1184c70a0a0e0d58c17a6e7ba527726045f2aed5caa31f56a`，原 preview MP4 `f76daf3065796ef847500041648f5dadb1cffa98898c466f11ac3471be9e8887`。FAKE parent report `b608ff8d5d5c22e18b49a967bd1d84d061892947d23951b2d47148d2d0608bf7`。

## W5 新完成：对 **实际 W3 两份媒体** 运行既有 W4 CLI（零 API）
独立使用 GitHub artifact download 取出两个 ZIP，先 `sha256sum` 再调用 `scripts/review_gpt_episode_offline.py`。**CLI/main 内容审查器均保持 GitHub 精确字节**：CLI blob SHA `5283a59e1e036ad45ecca1680c3f842724826473`，core blob SHA `e8da5b92e43569e2f3616fccce244dc0b04e5cef`；隔离运行时仅将 main 原 `offline_qa._subtitle_items`、`_stamp` 及相关常量原样提取作 import shim，避免加载无关 offline_render 模块；未修改 W4 源码或媒体。未导入或伪造任何人工 HMAC 签字。

| 核对 | 原版 | W1-FAKE |
| --- | --- | --- |
| Artifact | 12142320238 | 12141772943 |
| 最终 MP4 SHA | `d4208ccb7b4353e184eb7d003125a010e20f8dedf7a3a9bc0eee85a0e4f041f7` | `de6d623523d8537461571b66508ee997a28e10fed23cd927900c3f8370a6df2f` |
| SRT SHA（同内容） | `c6fa289f4a63192ea72d83c31dba86771fae10ee09a6ee68413ad78f7a259db6` | 同左 |
| 09_render exact-byte SHA | `364016304d078e11730b858956002eb7236cdf5282bc92dfa5f80a99cdada1ad` | `3296b63bf88f154a43efba6a8ad895243331de22a8633a7474f68b178677ecf4` |
| W4 `report_sha256` | `e8a6218d4f260e378d83cf886ecb1aebd972fc82ad41777aa777a8103cda9195` | `e1b2a69e4dc54bcfef45fd5efcdaf04a97fffed794f6eb7509f8f68c3fcaec10` |
| W4 CLI 运行结果 | technical=pass / content=fail / release=blocked | technical=pass / content=fail / release=blocked |
| 人审/可用/需修/未知 | 0 / 0 / 3 / 9 | 0 / 0 / 3 / 9 |

两片 `ffprobe` 均测得 **60.177333s**、H264/AAC/mov_text；12镜 W3 毫秒时间轴 **60,156ms**，与封装时长差 21.333ms，绝不互换；W5 新运行 FFmpeg 全片视频+音频解码均 pass。失败已记录：s03/s09 男主年龄漂移；原版 s07 三格分屏。FAKE s07 只是旧 s04，报告 reason `existing_s04_as_s07_fake_not_content_repair`，不继承原版 s07 历史分屏结论，亦不算修好。其余9镜各为 `unknown`。错误地将 original 目录用作 FAKE 输入被 CLI **exit 2 fail-closed** 拒绝。两版 report SHA 恰与 W4 历史 *hash-only baseline* 相同；本次增强点是输入真实 ZIP 直接运行。

实际离线复现命令（私有 media 只保留本地，不提交仓库）：
```bash
PYTHONPATH=src python scripts/review_gpt_episode_offline.py \
  --original-dir /private/w3-original --fake-dir /private/w3-fake \
  --original-artifact-id 12142320238 --fake-artifact-id 12141772943 \
  --original-sha d4208ccb7b4353e184eb7d003125a010e20f8dedf7a3a9bc0eee85a0e4f041f7 \
  --fake-sha de6d623523d8537461571b66508ee997a28e10fed23cd927900c3f8370a6df2f \
  --output-dir /private/w5-new-w4-qa
```

## 已有生产 CLI / I/O 缺口（不重写）
| 路径 | 真正证实 | 不可延伸的宣称 |
| --- | --- | --- |
| `run_gpt_video_three.py` | 历史三镜实生成；`--paid` 与当日费用操作参数；无 `--paid` 离线只列计划 | 不是全12镜后期审片命令；不得重新使用 USD5 |
| `complete_gpt_episode.py` | 已批准剧本/原三镜 + 剩九镜 artifact 重用或显式 `--paid`，完成片段与合成 | 未把生产 W2 manifest / W3/W4 人审/账单/发布自动整合 |
| `w1_single_shot_repair.py` | 真实旧素材仅可作 **existing-media offline simulation** 的修镜契约，11镜哈希保护 | 不具备真实计费单镜 Provider 修复授权 |
| `postprocess_gpt_episode_offline.py` | 实际真实 MP4 技术字幕/时间轴/原生音轨来源收据 | DRAFT SRT 不是 ASR 或口型正确 |
| `review_gpt_episode_offline.py` | W5 对两份真实 W3 artifact 已直接验 SHA/三门禁 | HMAC 不证明真人看片；无 Gemini 评分 |
| `fake_episode.py` | 已有 11 步 Fake JSON 一次打通、可复用接口 | **真实**11步“一命令”未证实 |

**`real_one_command_pipeline=not_verified`**：真实素材已按多个脚本及 workflows 跑成，但没有在同一正式批准剧本输入下证实一条 CLI 安全自动贯穿 12 镜→合成→审片→成本及发布门禁。不要把以上收费入口临时串联起来冒充通过；若将来有具体失败证据，仅由独立批准的 R4.4 补缺包给既有 `complete_gpt_episode.py` 添最薄只读/无费接口，不新建 orchestration/UI/DB。

## G4 北极星与出厂矩阵
| 门槛 | 本次证据 | 判定 |
| --- | --- | --- |
| ≥50% 合格镜头（12镜至少6镜真人判可用） | **真人签字=0；已证实可用=0；历史负例3；未知9**。不能把9未知算不合格或把0已验证当真实良率0% | **unknown / 未达验收证据** |
| ≤USD30 / 实际合格成片分钟 | 历史供应商实际 invoice **unknown**；真实合格时长 **unknown**。W1–W5 新付费调用0不代表历史视频收费0，USD4.27预测/已用USD5不等于实账 | **unknown / not_computable** |
| 单集人工操作≤2小时 | 无从梗概到可发布片的真实人工计时记录 | **unknown** |
| 实际中文对白、配音、同脸同声、口型、字幕对应 | 实际 ASR/听审/完整真人逐镜认定缺失，DRAFT 剧本推断字幕16句 | **blocked/unknown** |
| R4.3 Gemini 相邻镜头打分+人复核 | Gemini `not_run`，Issue #177 待独立型号、费用、隐私及权利许可；不能用 Fake/CI 替代 | **blocked** |
| 出版权利、人工发布批准、Owner G4退出签字 | `publish_approved=false`、G4未批准退出 | **blocked** |

### 最短剩余依赖路线（Owner 决策优先）
1. **Owner/人工审片者，零 API**：分别打开两份确切 SHA 的真实片，完整看/听，逐镜按 W4 10维做真实签字，优先复核 s03/s07/s09；取得至少6镜 genuine usable（不能复用另一版本的签名）。记录每次人工耗时。
2. **Owner / #177**：决定真实 Gemini 相邻 `s03/s04`、`s08/s09` 视觉评分及可选真中文 ASR 是延期还是提交经过单次费用上限、隐私/版权批准的独立授权；在授权前均 `not_run`。延期选项**不能**声称 R4.3 已达到正式要求。
3. **Operator / billing**：出示旧真实 Omni 视频供应商发票/收费回执，并按真人确认的*合格分钟*计算实际 USD/分钟；补从故事到成片的人工工时。
4. **受独立 G4 授权的 W1 owner**：如 s03/s07/s09 确需更换，仅请求严格限定单镜的新费用/任务收据与其他11镜不变验证；旧 USD5 权限不可复用。
5. **M5 + Owner**：把批准剧本→真实镜头→后期→内容QA各接口缺口单独验证，最终核对权益/配音与全部三项 KPI；Owner 明确写出 `publish_approved` 和 **独立 G4 exit decision**。未批准前持续 G4；W6/G5 不启动。

## 零新增费用与结论
W5 使用两份历史 Artifact、本机 FFmpeg/FFprobe 和 W4 CLI；**新付费模型调用 0 / 新模型 API 费用 USD0**。历史供应商实账 `unknown`；没有把旧授权转给 W5。真实内容质量与发布门仍失败/阻断，**最终结论：NOT_READY**。W5 文档工程可以按 CI/自治规则收尾，但 G4 **不得退出**。
