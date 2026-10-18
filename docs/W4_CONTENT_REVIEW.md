# G4 / R4.3 / W4 — real-shot content QA without paid inference

Stage: G4 / Req: R4.3 / Work package: W4 (M4). Issue [#175](https://github.com/Mrlukahuang/ai-short-drama-factory/issues/175). Source main `c5ed3314714523ced3c9c5391a4652289766ee8e`.

## What exists, and what does not

The separate W4 adapter `pipeline/content_review.py` consumes W3's existing `09_render.json`, `10_qa.json`, DRAFT SRT and final MP4 **read-only**. It does not change W1, W2, W3 source, old media, subtitles, producer calls, frozen TTS, database, workflow or release gate. Source `09_render.json` is checked against `10_qa.json.render_receipt_sha256` using **exact bytes**. The final MP4 and SRT are also byte-hashed; expected MP4 SHA must be provided independently. Exactly s01–s12, unique ID/order, SHA, contiguous measured millisecond intervals, SRT cue count/range and W3 technical flags must agree.

For the W1-FAKE branch, the verified original bundle is mandatory: parent clip SHA, source-response SHA, parent preview SHA and all 11 unchanged per-shot records are matched, and s07 must be the preexisting s04 bytes. The W1 simulation is **not** a valid quality repair. Use separate, version-bound observations; a signed review for one complete MP4 SHA or artifact ID cannot be re-used on the other.

Historical documented negatives are **not new W4 human views**: age/identity drift on s03 and s09, and the original s07 3-panel split-screen. The s03/s09 bytes are identical across both versions, so their **negative-only clip-bound evidence** appears in both outputs with its original source citation, without increasing W4's human-review count. The original s07 split-screen observation does **not** migrate to W1-FAKE s07; that replacement is instead explicitly `existing_s04_as_s07_fake_not_content_repair`. Nothing unseen/unheard becomes `pass`. No claim that production W2 asset manifest exists: null and `prompt_anchor_only` continue to apply.

The ten per-shot review dimensions are: `visual_character_identity`, `appearance_age`, `costume_prop_continuity`, `scene_camera`, `split_screen`, `overlay_text`, `voice_identity`, `expected_vs_heard_dialogue`, `lip_sync`, `subtitle_alignment`. Each accepts `pass|fail|unknown`, with default `unknown`. Any reason-coded failure gives `needs_repair`; all ten signed human passes are needed for `usable`; otherwise the shot stays `unknown`. The output includes measured timing, clip/media SHA, per-check statuses, reviewer, evidence provenance, original/fake variant, stable report SHA, prioritized repair hints for W1, and independent technical/content/release decisions. **Release is always blocked.** Neither `technical_qa=pass` nor favorable model scores may authorize publication.

## Run on already-downloaded W3 artifacts (no generation)

Use [Run 39141517448](https://github.com/Mrlukahuang/ai-short-drama-factory/actions/runs/39141517448): original Artifact **12142320238**, W1-FAKE Artifact **12141772943**. Unzip **locally** to separate directories, ensuring each contains `09_render.json`, `10_qa.json`, `draft-captions.srt` and `gpt-episode-caption-draft.mp4`. Do not commit media, frames, voice, private transcripts or operator secrets. No workflow rerun required.

```bash
python scripts/review_gpt_episode_offline.py \
  --original-dir /private/w3-original --fake-dir /private/w3-fake \
  --original-artifact-id 12142320238 --fake-artifact-id 12141772943 \
  --original-sha d4208ccb7b4353e184eb7d003125a010e20f8dedf7a3a9bc0eee85a0e4f041f7 \
  --fake-sha de6d623523d8537461571b66508ee997a28e10fed23cd927900c3f8370a6df2f \
  --output-dir /private/w4-qa-new
```

This writes only `original-content-qa.json` and `w1_fake-content-qa.json` to a **fresh output directory**, and prints summary SHA/counts. It does not write to the input trees. Without signed review import, *human-reviewed count is zero*, all audio/ASR/lip-sync/subtitle **content** scores remain `unknown`; known negative observations still produce priority repair suggestions. `technical_qa=pass` means W3 technical receipt + bytes were validated by this adapter, not that W4 independently re-ran FFmpeg.

### Local review & provenance

The W3-measured 12 shots occupy intervals [0, 5013), [5013, 10026), ..., [55143, 60156) ms. For each shot, use three bounded sampling positions at offset 500 / 2500 / 4500 ms (all less than the measured 5013 ms). Use the local MP4 in a player, or **locally**, if screenshots are necessary, FFmpeg `-ss` at `(start_ms+offset_ms)/1000` with `-frames:v 1`. The original AAC track is in the same MP4; inspect audio at the measured shot start. Do not publish samples or attach them to CI; check adjacent prior/next shots in the same version, especially s03/s04 and s08/s09. This review guide reuses existing FFmpeg functionality rather than implementing a second frame/audio extractor.

For positive **human-attested** records, prepare a private UTF-8 JSON object with exactly two arrays: `{"original":[...], "w1_fake":[...]}`. Each row has the following typed fields (one per shot/version): `artifact_id` (integer), `final_mp4_sha256`, `parent_final_mp4_sha256` (null for original), `shot_id`, `shot_video_sha256`, `start_ms`, `end_ms`, `srt_sha256`, `reviewer`, `reviewed_at` (UTC ISO-8601), `review_mode: "human_attested"`, `review_source: "local_media_manual"`, `evidence: {"note": "...", "watched_video": true|false, "listened_audio": true|false}`, `verdicts` with all ten checks, and `attestation_hmac_sha256`. The authenticated reviewer must explicitly watch/listen before marking the respective dimensions other than `unknown`. A script/model must not auto-fill “pass”.

The independent operator keeps a locally private random credential (32+ bytes, Unix file mode 0600; not a GitHub secret, not checked into repo). After writing the real review record, the **operator** computes `sign_review(record, credential_bytes)` and inserts the returned digest. Import only if that reviewer is explicitly authorized with `--reviewer operator-one --reviewer-key-file /private/secret-key` and `--reviews-json /private/reviews.json`. The verifier checks HMAC, all media IDs/SHA/timing, UTC timestamp, observed modality, complete verdicts and no duplicates. Wrong key, missing signature, stale version or “listened=false but voice pass” fails closed.

**Important security limitation:** HMAC proves possession of the reviewer credential and prevents an unsigned or altered record; it **cannot cryptographically prove that the human truly viewed/listened**. Reviewer credentials must stay exclusively with a trusted operator. If that cannot be guaranteed, leave the human verification status unknown and have the owner confirm directly. The CLI does not grant any publication or stage-exit approval.

## R4.3 Gemini visual precheck and real-ASR research gate

The historical production path uses independent Omni prompt-only shot generation, not production W2 reference image/audio injection. Existing `g1_benchmark_metrics.character_error_rate` can only compare words after a trusted, real transcript exists; DRAFT SRT derived from screenplay durations is **not ASR**. Neither this adapter nor W3 production has evidenced Gemini adjacent-frame/image scoring, provider request receipt, task ID, actual quota/spend or validated model outputs. Therefore both outputs explicitly state `visual_auto_precheck_status=not_run`, `gemini_adjacent_shot_scoring=not_run`, `asr_status=not_run`, `r4_3_exit_status=pending`. Do not mark R4.3 done based on Fake scores or zero paid calls.

For a later proposal: select *two adjacent pairs only* (s03/s04 and s08/s09), read-only downsampled local frames with operator source-rights clearance, evaluate exact API model and input-privacy policy, estimate cost/quotas and define request/response receipt, version-binding and known-negative calibration. **Get new, explicit owner authorization before any remote image, audio or ASR submission**, and do not reuse the already-spent USD5 video approval. If an operator supplies verified real transcript/time anchors later, benchmark CER separately and retain subtitle ASR provenance, without rewriting W3 SRT.

## W5 handoff / explicit blockers

- The exact source artifacts and hashes above; outputs are deterministic if local input bytes and signed reviews are unchanged. The historical negatives are prioritization, not an entire-film quality score.
- Content QA: known historical failures; no validated full-12-shot human passing; independent actual Chinese voice/dialogue, lip sync and subtitle matching remain **unknown**. Existing user feedback says dubbing is unsatisfactory, but does not establish word-level wrong text or per-shot voice diagnosis.
- Technical QA: W3 already did full decode; W4 rechecks the W3 receipts/bytes and refuses tampering.
- Release QA: blocked; `publish_approved=false`; G4 not exited. No Gemini precheck production pass or trusted ASR.
- W5 must collect **actual usable shots / duration**, actual supplier invoice (historical real-video bill is **unknown**, not USD0) and independently measured human review effort. Targets: ≥50% genuinely usable shots, ≤USD30 per accepted minute, ≤2 hours operator labor, plus explicit owner release/G4-exit decision. Unknown metrics must not be counted as zero or passed.
- Cost and rights: W4 new paid calls 0, new videos 0, incremental API USD0; no third-party code copied (prior OpenMontage idea-only). Rollback: revert this W4-only PR; W1/W2/W3 and their 09/10/media remain unchanged.
