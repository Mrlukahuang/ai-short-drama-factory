# CityDiscount G4/R4.4 — s05 真Omni金币CD字形进入 60s 独立审核版

2026-10-23 NZDT。Stage: **G4** / Req: **R4.4**。

## 源证据与实交付

用户曾在 Issue #188 明确希望 s05 第一枚金币刻上 CityDiscount 的 CD 字形。PR #247 完成了独立5秒审核镜头：真实 s05 清除虚构店牌后的历史Omni视频，经本地关键帧把**来自既有真实官方Logo片尾视频**的绿色 CD 字形贴到出现并被拾起的金币上。其独立 Github Actions **39778802932** 成功产出视频（Artifact **12426840158**），独立 MP4 原Sha `6b5c164834df7fd28b1c20fb917399136b1ac900478efef34c504aee63f8d9f7`，真实5秒/120帧H264/AAC。

本轮不是再生成小羊：对现有60秒 rev5 完整真实 FFmpeg/H264 编片器做**一个可选素材输入** `--s05-cd-coin`。仅在同时提供旧经过来源SHA验证的真实 s05 去字源 `--s05-clean`、且金币5秒文件与上述 SHA 完全一致时，才允许在时间轴 **s05 (20–25 秒)** 用该审核版替换。其余11段镜头保持原有rev5版本；仍输出60秒 1080×1440 3:4 H264/AAC、12镜实际视频帧 `CONTACT_SHEET_12_SHOTS.png`、来源 receipt 与 `visual_review.json`。使用现有唯一编片器和现有单个60秒GitHub Action，不制造重复视频框架。

> **源素材真实不等于整个60秒真AI**：s02/s05是历史真羊，s03是真Omni城市环境（原拉远旧片倒放），s04可选B只是同一张真实羊毛城市最后一帧的数字推镜且无羊动作，s01/s06–s11多数仍是本地XYZ样板。金币图层是手工近似关键帧，可能需要修正透视和边缘遮挡，不代表 Logo 专业商标最终过审。模型新生成调用0，历史 Google真实账单未知，新的第三方图片传输未批准。

## 双版本可比对与严格门禁

前一版本 [PR #246](https://github.com/Mrlukahuang/ai-short-drama-factory/pull/246) 原 s05 **没有CD字形**，仍保留为已核验A/B底片；本轮只追加 **Owner金币审核的独立完整60秒版本**，不覆盖任意源视频。新 GitHub Artifact 名称明确 `OWNER-CD-COIN-REVIEW` / `NOT-FINAL`。

回执必须满足 `s05_cd_coin_local_review_sha256` 精确值、`s05_coin_review_inserted_into_this_60s_cut=true`、`s05_coin_local_manual_tracking_not_owner_approved=true`、`s05_coin_exact_design_approved=false`、`publish_approved=false`。旧简单命令不带可选参数仍采用旧已核验去字s05，不能静默推广未经人审的金币。

合并须所有 Scope、Fake、Python3.11/3.13、libSQL、offline-video 及专项真60秒FFmpeg + 12帧图七项CI全部成功，再按 AMEND-004 自治。安全边界：参考媒体外传/新的付费运行仍受 [#188](https://github.com/Mrlukahuang/ai-short-drama-factory/issues/188)、[#210](https://github.com/Mrlukahuang/ai-short-drama-factory/issues/210) 未完成核验约束，G4 NOT_READY，G5冻结，正式发布禁止。

**未解决的真实主体镜头缺口没有随本次PR缩减**：12镜里扣除只有Logo的s12，还有11个表演位，目前只完成真Omni小羊 s02 与 s05，共 **2/11**，剩余九个真小羊镜头。s03虽是真城市环境但无羊动作，因此不算小羊表演完成。最优先新真实场景仍是s04，之后是s10–s11、s06–s09、s01；不能用新的数字变焦替代。
