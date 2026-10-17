# G4/R4.1: screenplay → Omni request preparation

The existing F3 runner uses a fixed six-shot story. Do not point it at an imported GPT screenplay and assume it consumes that screenplay. The new pure function `build_screenplay_video_plan` prepares all shots or an explicitly selected contiguous subsequence; it calls no providers and grants no approvals. No paid runner is added.

Inputs: a validated Screenplay, matching ScriptContext, style text and explicit actor appearance descriptions. Read style_prompt only from felt_diorama when desired; do not mix its old costume descriptions with the screenplay Bible. Appearance anchors are supplied data, not verified production asset versions. Unknown references, unsupported durations, missing anchors, excessive prompt length and reordered/noncontiguous selections are rejected. Persisted assets and natural-language continuity still need review.

Output: exact script action, camera, dialogue, speaker/timing and start/end continuity inside each prompt; 360p / 9:16 / URI request preview, per-shot hashes and source screenplay hash. These are proposed wire payloads, not validated generated videos. Prompt durations are desired timing; existing transport cannot enforce exact length. Do not automatically trim dialogue or claim final duration equals the 60-second script.

Cost preview uses the existing repository 360p snapshot USD0.0337925/second, not an invoice or newly revalidated 360p conversion rate. It reports desired-duration output-only estimates and a separate 10-second-per-shot scenario, excludes input/text/thinking/other costs, and always leaves total cost unknown, budget unverified and paid execution unauthorized. A below-USD2 output estimate is not permission to execute.

Real existing Sol output (Run39035812309/artifact12102675304) replayed locally:

| Selection | Requested duration | Desired output-only estimate | 10s/shot output-only scenario |
|---|---:|---:|---:|
| s01–s12 | 60s | USD2.0275500 | USD4.0551000 |
| s01–s03 | 15s | USD0.5068875 | USD1.0137750 |

Recommendation: prepare a separately scoped three-shot test first; no whole-episode launch, no reuse of F3 Issue137 claim. Need budget including inputs/thinking, same-day spend check, explicit actor/prop versions and a reviewed paid execution path before submission.

Official sources checked 2026-10-18 NZT: https://ai.google.dev/gemini-api/docs/models/gemini-omni-flash states output3–10s. https://ai.google.dev/gemini-api/docs/pricing lists input USD1.50/M, text output USD9/M and video USD17.50/M but its 720p example does not establish the 360p1931tokens/s conversion. Therefore the repository 360p arithmetic remains explicitly a snapshot estimate. https://ai.google.dev/gemini-api/docs/omni describes Interactions video generation; it does not make timing cues an exact-duration billing cap.

109 related local offline tests passed. Both full and first-three real-script plans prepared without paid calls; generated prompt JSON remains a private operator artifact, not committed to source control.
