# 当前交接状态（每个 Agent 结束工作时必须更新）

> 只保留**最新**状态。历史交接追加到 `docs/handoff/LOG.md` 末尾（每条 ≤ 10 行）。

## 当前阶段

**AMEND-006（Active）— F1 → F2 → F3**。ADR-010 已 Accepted：固定 `gemini-omni-1.1-flash` + 原生中文对白 + 奥克兰毛毡微缩 `config/style_presets/felt_diorama.json`。PR #133 已执行真实 3 镜风格试验，#132 已由所有者确认采用。P0–P-final 完成（最终 PR #131）。依据 AMEND-006，本方向的真实调用从 AMEND-005 暂停中解除，但仍受 AMEND-004 每次≤US$2、当天累计≤US$5 控制。

### 不变边界

- 每个 F 单独分支/PR；scope+全部 CI 全绿自行合并，更新本文件和 LOG；无需中途等待。
- **不修改** AMEND-001 冻结路径或治理文件，不新增 UI、不改小说、不解锁 TTS / TxLab canary。
- F3 实际费用须与预估分开记录；若供应商账单或可信费用上限不可核对，停止该付费测试并开 `[需要所有者]` Issue。不得拆分超预算请求。

## 下一个任务（按顺序，一次只做一个）

1. **F2（本 PR）**：`scripts/fake_episode.py --provider omni --style felt_diorama`；Fake 默认不变；沿用 P-final 11步 JSON、纯合成前四步、六镜原生音轨、逐镜哈希+拒绝未知付费任务自动重试。
2. **F3（F2 CI 全绿合并后）**：手动 Actions 工作流以360p跑6镜，预估总计≤US$2、当天累计≤US$5；真实合并 MP4 + 每镜元数据 Artifact，开 `[需要所有者]` Issue 交所有者看片。仅在安全额度、费用记录和密钥条件满足时执行，否则发 Issue 阻断并保留 F3 离线代码。

## 需要所有者决定的事（现状）

- #116 Seedance/Kling、#119 定妆照及 #120 多模型九镜仍保留备选，不阻塞毛毡方向。
- #132 已按 AMEND-006 接受三镜风格试片结论（预计 US$0.70，实际账单未在仓库中独立核实）。

## 最近一次交接

- 2026-10-16，GPT-6，**Stage: F / Req: F2**；F1 PR #135 CI 全绿，合并 SHA `826fe66fdf6421679d03a0936c1ce72c155b6794`。
- F2：`scripts/fake_episode.py` 新增 `--provider omni --style felt_diorama --paid`；Fake 默认保留；`scripts/felt_omni_episode.py` 串既有 P-final 的 00–04 Fake 合成剧本，真实/注入 Stub 的 05–10 六镜、原生音轨、竖屏技术检查与阶段 JSON。收费任务在发出前有硬预算预检，每镜有 started/complete 收据，绝不自动重投。
- **费用阻断事实**：Google 官方 360p 视频输出 1931 tokens/秒×US$17.50/百万≈US$0.0337925/秒。当前 Omni 旧适配器无法强制实际输出 6秒、最大可能 10秒，六镜最坏仅视频输出约 US$2.02755，已超过 AMEND-004 US$2/次（输入另计）。F2 不发真实请求，F3 必须先验证能严格封顶，否则按 AMEND-004 新建 [需要所有者] Issue。禁止使用累计估算代替真实账单。
- F3 仍待办；原生中文对白的音轨可通过 ffprobe 证明存在，但语音内容/字幕正确性仍需人工审片和转写。下一项仅 F3。

## 异议栏（Agent 对方向有不同意见时写这里，等所有者裁决）

（空）
