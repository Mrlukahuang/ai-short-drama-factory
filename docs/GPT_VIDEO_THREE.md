# GPT screenplay first-three video test (G4/R4.1)

Stage: G4 / Req: R4.1. Uses the existing approved-for-testing Sol screenplay, not the old F3 six-shot story. Produces three separate clips s01/s02/s03 only; no OpenAI request, no remaining nine shots, no silent whole-episode launch. Formal writer selection unchanged.

## Source and appearance

Workflow downloads original writer-first3-39035812309 artifact from Run39035812309 and verifies the Sol response canonical SHA256 c5665e198eb3d30110a0bb6dc30d5f2cfadf74979eb5e6e0596d64751ff1a6f9 before parsing. It reconstructs the exact comparison Bible and uses its actor anchors: forest-green apron/beige shirt for A-Jie and pale-yellow coat for Xiao-Yu. It reuses only the felt style text, not incompatible old F3 costume descriptions. These remain fixture/test identities, not version-verified production assets or visual reference images. Cup, cloth, jug and card must be checked visually after generation.

## Estimate and explicit owner risk decision

- Output scenario:3 ×10.1 seconds ×existing360p snapshot USD0.0337925 =USD1.02391275.
- Input reserve USD0.15 (100k token assumption across three prompts; prompt bytes limit is NOT a verified token bound).
- Additional text/thinking reserve USD0.25 (NOT a proven upper bound).
- Total estimate USD1.42391275; acknowledgement USD2, declared same-day spend +USD2 must be ≤USD5.

This is NOT a complete verified worst-case bound, not a supplier-enforced cap, and not an invoice. Actual billing may exceed the estimate/acknowledgement. The360p conversion is the old repository snapshot; current official pricing confirms video USD17.50/M but does not independently establish this conversion. No claim that input or thinking is hard-capped. Therefore this workflow must NOT be launched autonomously under the ordinary ≤USD2 rule: owner must explicitly accept estimate risk with both the exact confirmation and the separate checkbox. General “continue” is not silently converted to that acceptance. No generation has occurred while preparing this PR.

## Run once after review

Actions → **GPT screenplay first3 video test (manual, estimate risk)** → Run workflow on main:

- confirmation: `RUN_GPT_VIDEO3_ESTIMATE_USD2`
- accept_estimate_not_cap: true only if owner accepts the above uncertainty.
- reported_spend_today_usd: actual operator-checked same-day total API spend (Pacific/Auckland); do not guess zero.

Existing GEMINI_API_KEY is read only by the paid step. No new key is required. The current connector cannot dispatch Actions; owner must click once. Do not use Re-run jobs. The new one-time Issue146 marker is independent of consumed F3/text-pilot markers; none are reset or deleted. Duplicate marker, nonowner/nonmain context, run_attempt>1, missing acknowledgement/secret, stale dates or insufficient declared daily budget deny execution.

The Google SDK is configured explicitly with retry_options.attempts=1. SDK defaults would otherwise retry paid requests. Claim precedes provider creation/submission; in-flight report precedes each generation. Any generation, receipt or media error stops the batch, preserves the consumed claim and uploads incomplete report/recovery records. No automatic regeneration after ambiguity.

Success produces three original360p portrait MP4 clips with native audio and a report. Actual durations may differ from desired5s each. No time stretching, trimming or automatic concatenation is performed. Audio-track presence does not prove Chinese dialogue/voice correctness, and source provenance plus structural validity do not prove story quality. Human review remains required. Actual fee stays null until billing reconciliation.

## Offline validation

129 related local tests passed plus compileall. Tests use synthetic provider/media results and prohibit real network; they are not evidence of actual video generation. Coverage includes default-off CLI, source hash mismatch, SDK retries disabled, owner/risk/daily gates, persistent claim and stop-after-first-error. This PR adds no real call and does not rerun old workflows.

Official SDK reference checked: googleapis/python-genai google/genai/types.py HttpRetryOptions defines attempts1 as no retry (default5). Provider docs: https://ai.google.dev/gemini-api/docs/models/gemini-omni-flash and https://ai.google.dev/gemini-api/docs/pricing .
