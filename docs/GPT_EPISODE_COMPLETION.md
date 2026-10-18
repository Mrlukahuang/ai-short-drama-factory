# GPT twelve-shot completion (G4/R4.4)

Prepare all remaining pipeline work in one path; appearance refinements deferred by owner. New workflow is manual only and has not been executed.

## What runs

Download original Sol writer artifact (Run39035812309) and already completed first-three artifact (Run39047208593). Verify fixed writer-response hash, fixed original first-three report hash and all original clip hashes/durations before any paid claim. Reuse s01/s02/s03. Request ONLY s04–s12 (nine calls, no model retries). Preserve per-attempt report and recovery receipts. On complete success stage12 original clips, concatenate native video/audio, fully decode and emit delivery/gpt-episode-preview.mp4 plus delivery.json. No new OpenAI text call.

No old claim is removed/reset. Remaining-nine uses a separate marker and confirmation; previous three-shot confirmation cannot authorize it. Nonowner/nonmain/attempt>1, missing risk acknowledgement, stale snapshot or insufficient declared daily budget deny before submission.

## New authorization decision required

The new nine-call run exceeds ordinary AMEND-004 USD2 autonomy. Estimate:9×10.1s×old360p snapshot0.0337925 =USD3.07173825 video output; input reserve0.45 plus text/thinking reserve0.75 →USD4.27173825. These reserves/conversion are NOT proven billing upper bounds; no supplier hard cap. Requested one-time acknowledged allowanceUSD5; owner must accept the estimate uncertainty. Ordinary “continue” is not that authorization. No new model call was made preparing/testing this PR.

Actions → **GPT episode completion remaining9 (manual, USD5 estimate risk)** → Run workflow on main:
- confirmation: `RUN_GPT_REMAINING9_ESTIMATE_USD5`
- accept_estimate_not_cap: true only after owner accepts above uncertainty.
- reported_spend_today_usd: operator-checked same-day API spend in Pacific/Auckland; declared spend+USD5 must be≤USD5. With this reservation, any positive existing same-day spend blocks the run. Do not guess zero or omit other workflows' spend.

Current connector cannot dispatch this workflow; owner must click once. It reuses existing GEMINI_API_KEY; do not supply a new key. Do not click Re-run. Failure leaves the claim consumed and preserves partial output; no automatic paid continuation or individual-shot repair is enabled in this change.

## Offline delivery-only recovery

If all9 new clips completed but staging/assembly failed, download that artifact and run with a NEW output directory:

```bash
python scripts/complete_gpt_episode.py --writer-dir /path/to/writer --prior-dir /path/to/prior3 --generated-dir /path/to/completed-new-shots --output-dir /path/to/new-output
```

This mode never calls a provider. Default CLI without --paid or --generated-dir performs only source verification and prints an offline plan. --paid and --generated-dir cannot be combined. Incomplete nine-shot input is refused, not regenerated. Reports/delivery distinguish9 attempts in the new source batch from3 reused shots and0 calls in the offline assembly itself.

## Validation and limitations

140 related local tests +compileall passed. Existing real Sol+three-clip artifacts passed default offline preflight, showing exactly9 new IDs and3 reuse IDs,0 calls. Synthetic FFmpeg12-clip staging/assembly also passed; its36-second duration correctly fails60–90s eligibility. Actual remaining9 have NOT been generated. Actual invoice fees remain unknown.

All12 shots present and duration60–90s are reported separately; neither grants publication approval or stage exit. Exact5s per clip is not enforced. No trimming/stretching, dubbed voice, subtitles or music is fabricated. Stream incompatibility fails delivery for offline handling instead of triggering new generation. Dialogue/visual/subtitle quality remains pending. G4/R4.4 still requires real full-episode verification and the scoped failed-shot repair capability before declaring complete.
