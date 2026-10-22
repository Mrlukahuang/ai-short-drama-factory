# G4/R4.4 | 让真实毛毡奥克兰 s03 进入 CityDiscount 60秒广告技术片

**2026-10-22 NZDT，重用历史真源，新增模型付费调用0。**

## 真实画面对比的结论（已核对视频帧）
从历史 GitHub Actions run `39441034483`、Artifact `12274786001` 重新取得由 `gemini-omni-1.1-flash` 真实生成的 `s03-real/s03_city_plate.mp4`，原始 SHA256 **`b718e6b0a6e5a64db66d74e6b1364326d16671823fca12935e8a3667b101af3f`**，ffprobe **360×640／24fps／120帧／5.013秒**。画面包含真实毛毡材质的奥克兰天空塔、海港大桥、蓝色水湾、帆船及沿岸立体建筑；明显优于最新#243全60秒视频中s03的单色程序XYZ方块城市。

**关键实际限制：** 这段旧 Omni 真实视频的原始机位是从天空塔一带缓慢向远处**拉远**。用户需要从微缩城市远景**推近**街区。仅进行本地 FFmpeg `trim→reverse`，把真实的同一段毛毡城市视频反向播放，实现真实材质的视觉推近。原模型`s03` **不包含小羊**（source receipt `mascot_character_reference_applied=false`）；此次不是新模型镜头、不是生成了真实小羊、也没有确认 s03→s04 视觉上完全接通。

## 交付物与不碰的区域
在已经成熟的 `scripts/build_citydiscount_rev5_60s_moving_previs.py` 添加可选 `--s03-city`，只接受历史真实SHA校验过的源 MP4，失败直接阻断（不允许合成素材冒充真实）；固定位置 **10–15秒／s03**。对原360×640图像进行180°方向的时间逆序（并非空间图像倒置），原画中心用**810×1440**等比呈现，左右各135px以**原片同帧**虚化延展到1080×1440，FFmpeg输出24fps/120帧/H264/5.0s、不使用原片未审音轨。旧片s02仍是真小羊，s05仍使用已经验收去掉幻觉店名的真小羊，s12仍由旧毛毡地球渐变至官方Logo；其它8个本地程序视角**不改动**。继续从同一个60秒编片命令构造 H264/AAC 原创临时音轨整片，实抽12镜 `CONTACT_SHEET_12_SHOTS.png` 和来源回执。

为了防止将**源文件反放**夸大成专业动画，机器回执明确标记：
- `s03_genuine_existing_omni_environment_in_60s=true`（确实是真实旧模型城市）
- `s03_original_camera_crane_out_retimed_in_reverse=true`（仅逆序旧远景）
- `s03_has_original_mascot_performance=false`
- `s03_s04_unbroken_real_world_camera_verified=false`
- `real_model_generated_shots_added_in_this_run=0`
- `existing_real_AI_lamb_shots=["s02","s05"]`，不会把s03虚称为第三段真实角色表演。

## 创意/费用/发布门禁
真正理想的镜头是**实拍般的连续s03→s04**：从毛毡奥克兰远景降到同一个有地理连续性的超市街区，再跟着比例一致的小羊前进。本轮只能提升实际真实环境质感；现有 **s04仍是程序化XYZ城市**，s03→s04有可能存在风格跳切，须由Owner审看。原s03反放的帆船/闪烁点可能与真实物理时间方向不符，不能称作完整真实摄影机原生生成过渡。

没有新的媒体外传、账户/图权授权、TTS、真实Google账单结算或模型付费执行；真角色表演仍s02/s05共2段，缺失的9段角色表演未被虚构为已完成。全仓CI/专项实际60s MP4/12镜图需成功后才自治合并。**G4 NOT_READY，G5冻结，不能发布**。新生成真正s04与连续性需要Owner #188 / #210 的新素材与费用门禁。

源证据：`config/pilots/citydiscount_real_video_replacement_rev5.json`、原`s03-real/receipt.json`、真实CI视频产物及Owner私密备份。
