# PR-10f｜一次性真实 Gemini TTS 虚构短句冒烟测试（低于 USD 2）

## 实际远端测试结果：成功，授权永久消耗（2026-10-14）

- [真实 GitHub Actions #38525869818](https://github.com/Mrlukahuang/ai-short-drama-factory/actions/runs/38525869818)：`workflow=tts-one-use-canary.yml`、一次原始 main merge push、`run_attempt=1`，真正执行名为 “Generate ONE original fictional short phrase, never retry on unknown ACK” 的 Job，**completed/success**。事前 GitHub SHA 历史检查、受限依赖安装、私有 Secret 存在校验均成功。
- 实际脱敏回执：`remote_tts_attempted=true`、`remote_wav_format_verified=true`、`paid_request_attempts=1`、`model=gemini-3.8-flash-lite-tts`、`prebuilt_voice=Kore`、`wav_duration_seconds=3.56`、`wav_sha256=5a314b80d25cc9baa33939499b96de77574e0fdbea56a541fbf9a8cb8ce7db10`。
- 原创静态短句，没有发送用户小说或演员声音。`original_user_content_submitted=false`、`production_database_touched=false`。Google 并未在此 GitHub 测试中提供账单最终核对证据，因此 `vendor_billing_verified=false`、`vendor_hard_spend_cap_verified=false`，不推断具体实收美元费用。
- 真正 [WAV Artifact #11875741551](https://github.com/Mrlukahuang/ai-short-drama-factory/actions/runs/38525869818/artifacts/11875741551) 已验证存在，为 GitHub 私有 3 天下载；可能到期。**真实单声线 TTS 技术链路连通不等于声音商用许可、角色语义准确、成本总账或多角色生产 TTS 完成。**
- 此授权已经消耗。工作流随后在安全收尾 PR 加上 `if: ${{ false && ... }}` **永久硬锁**。不能重试本次测试，不能通过改写确认词再发出同样的已授权请求。



## 唯一已允许的外部调用

用户已明确授权**预计单项总成本不超过 2 美元的测试**，只有超出预算才询问。此实验仅针对 Google Gemini `gemini-3.8-flash-lite-tts` Interactions API **一次**，使用全新原创虚构句子 `Hello from a fictional short film.` 和官方预设声音 `Kore`；不会发送小说原文、角色/演员声纹、真实用户台词、文件、数据库或带授权的媒体给供应商。按 [Google 官方费率](https://ai.google.dev/gemini-api/docs/pricing)，这一句预期费用显著低于 USD 2，但**GitHub 不能限制 Google 最终账单、也不能提供供应商实际费用证明**。如果费用上限无法确定且将明显超过 2 美元，绝不能启动更大的真实实验。

## 一次性强约束

全新 `.github/workflows/tts-one-use-canary.yml`，仅当此 PR 的**唯一合并 commit** 包含专用 `PR10-ONE-REAL-TTS-20261014` 标记且 Workflow 新增到 main 时由 push 触发。唯一 Job 要求：`main`、`run_attempt=1`、同一 SHA 的 workflow 历史只能出现 1 条、无并发取消、无 workflow_dispatch 或定时任务、6 分钟上限、私有 GitHub Secret `GEMINI_API_KEY` 存在才可发起请求。CI 中的普通 push / PR / main 不满足路径和标记，不会触发付费工作流。**失败或者成功都不允许重新执行原 Run**。

Python 入口 `tts_canary.py` 在 SDK 客户端前复核完整确认词、2.00 USD 上限、自主付费标志、main 和 attempt=1；一次仅执行 `client.interactions.create(...)`，不包含循环、重试和自动恢复逻辑。若网络断开或 API 出错，供应商可能已计费，因此返回固定的‘结果不确定，不可重试’错误；不输出 token、请求正文、HTTP 错误或私人路径。仅在得到官方 Base64 WAV 并通过独立 24kHz/单声道/16-bit PCM、时长与字节数验证后，才上传最短 3 天的**私有 WAV Artifact** 与脱敏结果。真实账单、声纹商用权与生产可用性始终标记未验证。

## 必须立即安全收尾

无论本次真实 Workflow 是成功、失败、跳过还是密钥缺失，结果验证后立即再开一个独立 PR，将此 Job `if: ${{ false && ... }}` **永久硬锁止**，并更新 Roadmap 的真实状态证据。之后重新运行 Workflow、GitHub 手工重试和再次付款均无效。真实任务调度/恢复、角色授权、双角色配音和生产部署绝不因单句演示成功而解锁。

## 本地回归

Fake Interactions Client 需要证明：可只调用一次、完整官方 schema、真实 WAV 字节校验、二次覆盖前拒绝、预算/权限门禁拒绝、异常 ACK 只返回脱敏错误、无自动重试；全部普通 CI 没有 Google 凭据或付费 Provider。
