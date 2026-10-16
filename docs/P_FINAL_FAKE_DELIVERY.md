# P-final：全 Fake 一命令成片验收与 CI Artifact

> **AMEND-005 / P-final / STAGES R4.4 仅 Fake**。无真人、无真实模型、无收费、无版权或播出许可；这只是检验本机生产链路、中文分镜时间槽、字幕和 FFmpeg 解码的技术样片。

## 本地运行（完全合成的测试素材）

安装项目的离线测试依赖及 FFmpeg/FFprobe 后：

```sh
python scripts/fake_episode.py tests/fixtures/p_final_synopsis.txt \
  --output-dir artifacts/p-final-local \
  --duration 60 --acknowledge-fake-approvals
```

上面的明确开关只授权**程序生成的 Fake 角色和测试剧本**通过仓库原有两道本机审批 API，**不是**对真实演员、版权或上线的审批。程序读取本地 UTF-8 原创梗概，走 P1 Bible、P2 screenplay、P3 SQLite Fake 资产、P4 单镜 Fake 媒体、P5 非人声 WAV/中文字幕/合成背景音，最后导出带持续可见 `FAKE ONLY - NOT AI VIDEO` 标记的 H.264/AAC/mov_text MP4。

每个运行目录下保存 `00_input.json` 至 `10_qa.json`；每份 JSON 的来源及输入 SHA256、payload SHA256 可重新验证。再次执行相同命令应复用已经检查哈希的 P4/P5 媒体及完整 MP4；可以用 `--rerun-from 06_dialogue` 指定从某步及下游重跑。没有删除/重建既有数据库表、向云端发送视频/语音或申请密钥。

## GitHub Actions 凭证与工件

新增 `.github/workflows/p-final-fake-episode.yml`（**push main / PR**，无 secrets）使用固定合成文本、安装与项目现有 offline-video 同一 SHA256 锁定的 FFmpeg/FFprobe 工具。CI 从源文本实际执行完整 60 秒 CLI，使用独立脚本 `scripts/verify_fake_pipeline_artifact.py` 校验十一份 JSON 文件/源哈希、最终 MP4 SHA256、容器格式、H.264/AAC/mov_text 字幕轨、60 秒长度、分辨率及始终为 false 的真人/发布声明。CI 再次运行同一 CLI，通过 `cmp` 检查产物哈希确定性。

工作流使用 `actions/upload-artifact@v4`，输出 **`p-final-fake-full-episode-mp4`**（14 天保留）：

- `episode.fake.mp4`：本机 Fake 镜头卡、非人声提示音、合成音乐、中文字幕；每帧明显打 `FAKE ONLY`；
- `episode.sha256`：可复核原始二进制 SHA256；
- `stages/*.json`：十一阶段 JSON，含技术 QA、不包含原始小说、真人脸/声、Secrets 或实际付费调用。

**只有 CI 实际完成、artifact 确实可访问并且 PR 已合并**，才按照 AMEND-005 创建一次标题 `[需要所有者]` 的 Issue，提供**真实** Actions artifact 页面链接，提议 Omni 360p 单次真实端到端测试，预估 ≤US$3。这个数字不是供应商硬预算保证，**绝不自动执行**真实调用。现有 #116/#119/#120 按所有者要求继续挂起不处理。

Fake 整链通过不构成 G1 真实盲测、真人一致性、独立版权或商用许可验收。
