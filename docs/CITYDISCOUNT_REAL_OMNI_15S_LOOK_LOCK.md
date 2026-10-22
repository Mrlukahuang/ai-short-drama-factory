> 2026-10-22更新：原 #241 的15秒**历史基准**包含未核准店名，现统一改为使用PR #242通过SHA验证的原真Omni s05去字版（SHA `7a4a7e5f261a641dd7035698a5aad3a9a331bf51a70c5ccd7565677a2694a652`）。原视频SHA/源权属链仍保持不变，绝不冒称这是新AI生成。后续统一以无店名的15秒标杆参考艺术质量；仍不代表s03/s04的实拍已生成，也未批准金币/播出。

# CityDiscount G4 R4.4｜原版真实毛毡小羊的 15 秒视觉基准片

**制作日期：2026-10-22 NZDT**。这个交付用于确定下一批真实 Omni 镜头应达到的外观标准，**不是从低多边形城市预演中自动提升而来的真实三维广告**。

## 输入源与真实编码

本地和 GitHub Actions 使用下列已有、独立SHA校验的素材，不额外生成任何模型视频：

| 顺序 | 素材 | 真实性 | 源 SHA256 / 形式 |
|---|---|---|---|
| 0–5 秒 | s02 小羊出发 | **历史真实 Gemini Omni 角色动态** | `a8a25ba43e5e8659d9c5528d685c69e8e0f991b990a48bf77c5c2be4fcfef80c`，360×640，5秒 |
| 5–10 秒 | s05 超市挖掘 | **历史真实 Gemini Omni 角色动态** | `4ed60c4e769ab36e21186733931e89c23d1dcbb776e3274389216a2bb742fc56`，360×640，5秒 |
| 10–15 秒 | s12 地球→官方Logo | 已SHA确认的**本地二维地球示意与官方原版Logo** | `273516cacbc07d750fd0262de6897ddd3a879ed5e22fa58fd1f5a49e09c6b8c1`，1080×1440，5秒 |

程序 `scripts/build_citydiscount_real_omni_15s_looklock.py` 用 FFmpeg 严格SHA检查原文件、检查实长和宽高；原360×640视频缩到 **810×1440 不拉伸**，空余135像素/边用**相同源画面背景模糊延展**（并非新生成的街区），三段本地编码为 **15.0秒，1080×1440，24fps，H264/AAC**。声音为**刻意静音技术画质基准**，不使用eSpeak/未经授权歌曲。片尾原文 **“都市折扣🌟，您的省钱助手小羊薅薅。”**，Logo准确像素由原官方片尾提供。无需新的模型账号、密钥、付费、模型素材外传。

GitHub Action `.github/workflows/citydiscount-real-omni-15s-looklock.yml` 只读取 s02/s05 原历史真实 artifacts 和旧s12本地Logo视频；上传本次可播放的15秒参考片+机器可读的来源receipt。历史 artifacts 的7天过期问题已经有Owner聊天私密ZIP备份，切勿将原始AI图/私密权限凭证添加到公共仓库。

## 真人类视觉审查：什么才是后续场景需要匹配的

- 参考 **s02**：原版小羊的脸型、眼睛距离、体型、卷曲羊毛颗粒与鼻口、绿色围巾与小铲，以及自然转头/奔跑；实际小羊可能与原参考PNG定妆尚有差异，**Owner尚未逐帧确认身份锁定**。
- 参考 **s05**：超市实景的毛毡蔬菜/蔬果摊、柔和真实电影光、景深，以及羊在前景挖土的表演。可能出现未经核准的店铺招牌文字，**不能视为商家真实合作或批准的台词/Logo**。
- 参考 **s12**：**官方真实Logo本地合成**，至少停留3.4秒；地球仍是**二维画片**，尚无真正的奥克兰街区拉远变成真实立体星球的摄影机连续镜头。
- 针对待生成的 **s03/s04、s10/s11**：仅在Owner另行核准素材权利和真实费用后，才以以上原版羊及毛毡质感为身份/美术基准，制作同地理街区真实摄像机穿行；不能把现有低多边形动画冒称生成结果，也不能让模型随机换羊。

## 必须坚持的关卡

`real_character_footage_shots=2`；`remaining_real_character_footage_shots=9`；`new_model_calls=0`；`actual_historical_invoice_usd=UNKNOWN`；`allowed_new_reference_uploads=false`；`commercial_release_approved=false`。G4 NOT_READY、G5暂停。只有Owner真实图像使用/供应商传输权限和实际计费审批明确后才能开始下一次真实模型提交。参考 [PR #240 的九镜连续性计划](../config/pilots/citydiscount_real_video_replacement_rev5.json)、[Issue #188](https://github.com/Mrlukahuang/ai-short-drama-factory/issues/188) 与 [Issue #210](https://github.com/Mrlukahuang/ai-short-drama-factory/issues/210)。

**重要：** 本15秒片只有旧 s02/s05 是真实角色动态，不能谎称15秒影片“全部都是新的AI镜头”；也不能据此宣称60秒片已经完成。该片只用于审核参考，不是对外广告发布。
