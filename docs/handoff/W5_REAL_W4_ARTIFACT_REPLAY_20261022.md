# W5 / G4 — Original + W1-FAKE REAL historical W3 artifacts → existing W4 CLI offline smoke

Stage: G4 · Req: R4.4/R4.3 contract · Work package: W5 evidence closure

## Why this run is different

Existing W3 evidence has validated **two real generated 12-shot technical videos**, original and W1-FAKE repaired. W4 source code already implements `load_w3_bundle/assess_bundle`, but W5 Issue #179 requires **real direct execution of the W4 CLI on those exact two historical GitHub artifacts** rather than inferring it from unit tests or hash-only baseline emulation.

No new product orchestration, provider feature, SDK secret, media generation, database migration or UI. Use the existing W4 CLI, not a new evaluator.

## Frozen original bytes and versions

From [W3 standard handoff](W3_EVIDENCE_20261019.md) and old [Actions run #39141517448](https://github.com/Mrlukahuang/ai-short-drama-factory/actions/runs/39141517448):

| Input | Original | W1-FAKE |
|---|---|---|
| GitHub artifact ID | 12142320238 | 12141772943 |
| Source MP4 SHA256 | `d4208ccb7b4353e184eb7d003125a010e20f8dedf7a3a9bc0eee85a0e4f041f7` | `de6d623523d8537461571b66508ee997a28e10fed23cd927900c3f8370a6df2f` |
| `09_render.json` SHA256 | `364016304d078e11730b858956002eb7236cdf5282bc92dfa5f80a99cdada1ad` | `3296b63bf88f154a43efba6a8ad895243331de22a8633a7474f68b178677ecf4` |
| Subtitle `draft-captions.srt` SHA256 | `c6fa289f4a63192ea72d83c31dba86771fae10ee09a6ee68413ad78f7a259db6` | same |

Operator independent double check in current session: both source ZIPs downloaded from the exact Actions run, each MP4/SRT/09 receipt SHA matched, original FFprobe: 360×640, 60.177333s, H264/AAC/mov_text. Existing old 12-shot footage, *not CityDiscount s02/s05*.

## Enforced REAL W4 execution — verified success on GitHub Actions

[PR #230](https://github.com/Mrlukahuang/ai-short-drama-factory/pull/230) merged main `1384406a0e991c6776a92799a0750b7c52a23c12`. **Actual direct real-media W4 execution PASS** on PR head [Run #39625584995](https://github.com/Mrlukahuang/ai-short-drama-factory/actions/runs/39625584995); all seven check-runs completed SUCCESS. This is independent of earlier local hash-only reports and was repeated in a true GitHub hosted runner. Earlier [Run #39625063733](https://github.com/Mrlukahuang/ai-short-drama-factory/actions/runs/39625063733) also succeeded, and produced [report-only Artifact #12356388684](https://github.com/Mrlukahuang/ai-short-drama-factory/actions/runs/39625063733/artifacts/12356388684). The first W5 workflow CI attempt lacked ffmpeg on runner; fixed by reusing the existing hash-pinned offline FFmpeg wheel. No new provider calls.

Actual direct existing W4 CLI reports matched **exactly** the prior W5 inventory baseline:
- Original `report_sha256=e8a6218d4f260e378d83cf886ecb1aebd972fc82ad41777aa777a8103cda9195`.
- W1-FAKE `report_sha256=e1b2a69e4dc54bcfef45fd5efcdaf04a97fffed794f6eb7509f8f68c3fcaec10`.

The authoritative W5 machine-readable exit report **already exists** at [G4_ACCEPTANCE_20261019.json](G4_ACCEPTANCE_20261019.json) and remains `NOT_READY`. Follow-up G4/W5 CI adds a **cross-check from the freshly executed real W4 JSON back to this frozen acceptance inventory**, including true report-file SHA, preventing later contradictory acceptance summaries. We deliberately do **not** create a new acceptance system.

The workflow `.github/workflows/g4-w5-real-w4-artifact-smoke.yml` on PR and merge:

1. Downloads two exact artifacts from Run #39141517448 with GitHub's read-only Actions token; no Provider credentials.
2. Re-verifies frozen MP4, render receipt and SRT SHA pins. Physically FFmpeg-decodes existing two 60.18 second MP4s.
3. Executes `scripts/review_gpt_episode_offline.py` **once against both** W3 artifact directories. No `--reviews-json`, `--reviewer` or credential file. Does not forge human review.
4. Checks W4 report: `technical_qa=pass`, `content_qa=fail`, `release_qa=blocked`, zero usable human-attested shots, **9 unknown + 3 historical negatives s03/s07/s09** in both versions. s07 must differ between original and W1-FAKE; the other 11 original clips must be unchanged. W1-FAKE s07 still not content-fixed.
5. Uploads **report JSON only**, never source MP4, audio, private images or provider keys; saves true W4 JSON report SHA. If exact W3 artifacts have expired or required evidence is missing, workflow fails CLOSED rather than silently substituting Fake files.

This is a W5 technical evidence increment, **not W4 creative sign-off**, live Gemini scoring, real Chinese ASR, human content/voice QA, rights/release, or G4 exit. Historical actual provider billing is still unknown. Zero new paid requests (the GitHub Actions runner itself consumes normal CI resources).

## Next blocked decisions

Owner must independently decide human shot review of 12 actual clips; approve/authorize any third-party face/voice analysis, reconcile provider invoices and publication/brand rights. Stage G4 stays **NOT_READY**, G5 paused. PR, Actions runs and both actual W4 report SHA are now recorded above; content and release gates are still blocked, not promoted.
