# CityDiscount G4/R4.4 — 已核验的真实 s05 去字素材正式接回 60 秒技术样片

**本轮唯一目标**：沿用既有 rev5 的 12×5 秒 60 秒（1080×1440／3:4）编片器，**不新增低多边形/模拟角色**，把 PR #242 验收成功的真实 Gemini Omni s05 镜头局部去字版本用于 20–25 秒段。其余所有镜头源 SHA、城市场景程序、Logo 片尾与时间码均不改变。

真实素材来源：
- 旧原片 s05：sha256 `4ed60c4e769ab36e21186733931e89c23d1dcbb776e3274389216a2bb742fc56`。真实 Omni 角色表演，**原视频始终保存不覆盖**。
- 独立后期去掉幻觉商店名的 review：sha256 `7a4a7e5f261a641dd7035698a5aad3a9a331bf51a70c5ccd7565677a2694a652`。来自 GitHub Actions Run `39747140543`、Artifact `12411802702`，5秒120帧，**不是新的 Omni 模型输出**。
- 原rev4 60秒SHA仍为 `e65d01356dcc977ab40c6cfea2ed479b812b8d16ffae6ccc41bfde8ce430288e`；原官方片尾源为 `273516cacbc07d750fd0262de6897ddd3a879ed5e22fa58fd1f5a49e09c6b8c1`。

现有 `scripts/build_citydiscount_rev5_60s_moving_previs.py` 支持 `--s05-clean <exact MP4>`。该参数必须严格 SHA 验证，不符立即阻断；s05 通过 `extract_clean_s05()` 把原360×640的9:16来源**仅缩放为810×1440正中**（羊脸和身材不拉伸），空余两侧用**同一旧视频源的虚焦帧**填充至1080×1440，兼容已有12段H264连续合成。s05 替换仅视频片段，整个60秒仍采用既有本地临时音乐音效；**原始s05真实音频未带进成片**（回执明确标示），不能冒充完整真人中文配音已达标。

GitHub已升级原有 60秒专项工作流，不再新增平行编片基础设施：下载旧 rev4 和官方Logo及新的去字 s05，实际编码整片，FFprobe时长检查、SHA封条、输出12镜真解码抽帧 `CONTACT_SHEET_12_SHOTS.png`、machine receipt与`visual_review.json`，上传单独命名新Artifact供Owner观看。

**诚实边界**：仍仅 s02/s05 两段角色动作为真实 Omni，s03–s04、s06–s11等九个角色镜头仍是本地3D几何技术预演；片尾仍为二维毛毡地球＋官方Logo；未核实s05两个铲土动作或官方金币标准；家庭定妆、中文真实口播和视觉美术未完成人工验收。新增付费模型调用 **0**；历史 Google 费用 **UNKNOWN**，新图外传/模型费用仍由 #188/#210 控制。**G4 NOT_READY、G5停止、严禁正式发布。**

合并规则：全仓Scope/Fake/Python 3.11+3.13/offline-video/libSQL与专项真实60秒 H264/AAC + 12镜抽帧均成功，再按AMEND-004合并；如失败停下来修正，不用旧产物冒充新成片。
