# CityDiscount G4/R4.4｜真实Omni s05 店铺虚构英文招牌清理

Stage: G4 / Req: R4.4 · 2026-10-22 NZDT

真实 Omni 原片 s05 SHA256 `4ed60c4e769ab36e21186733931e89c23d1dcbb776e3274389216a2bb742fc56`，历史 run `39596195021`、Artifact `12343403535`。原片实际5.013秒、360×640、24fps、120视频帧；小羊在毛毡蔬果摊前挖掘，3.25秒左右出现金色圆币。

逐帧发现：小羊后方店铺牌匾有模型虚构的英文 **Checlues**，不能代表真实合作商家、CityDiscount商标或获准广告文字。新 `scripts/citydiscount_s05_sign_redaction.py` **仅对已有真Omni原视频做本地后期**：严格原片SHA检查，在 `(133,196,227,236)` 画出不带文字的浅棕羊毛毡内牌，不改原视频文件、不上传素材到外部模型，不主动覆盖小羊、土堆、金币、房屋和蔬菜。产物为新的 5 秒H264视频，连带原来音轨、前后对照JPG、回执。原片和修订版不同SHA保留，绝不混淆身份。

本地真实FFmpeg验收：120帧，5.0秒，主体原区域像素平均变化2.49/255，目标牌匾平均变化约35.84/255。不同FFmpeg版本允许轻微像素偏差，但超出区域变化阈值须阻止输出。新独立GitHub Actions工作流从**历史原素材Artifact**取源，必须重复SHA与实视频校验，再上传可观看的MP4和对照。

**未通过的创意/治理关卡：**小羊真实源虽然完整，挖掘是否正好两次、CD金币标准图案、品牌授权、发布日期/商用公开发布均**尚未验收**；`coin_exact_official_design_approved=false`、`two_digs_owner_creative_review=NOT_VERIFIED`、`commercial_release_approved=false`，G4 NOT_READY / G5冻结。新AI生成次数0、新付费0、新原始图片外传0。下一批真实九镜仍受 Owner #188 和 #210 门禁保护。

这是**修正一段已有真实5秒片**，不是新增的AI视频场景、更不是完整60秒广告完成。