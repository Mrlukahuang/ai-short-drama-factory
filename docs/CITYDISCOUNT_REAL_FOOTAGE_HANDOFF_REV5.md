# CityDiscount G4/R4.4 | Real Omni footage replacement gate after rev5 review

**2026-10-22 NZDT · current film: PR #239 (60.0-second 1080×1440 hybrid 3D internal technical PREVIS)**.

## Objective correction after visual review

The procedural XYZ town works as a **camera path sketch only**. Its blocky wool facades / hybrid PNG face are visibly far below the genuine warm felt/stop-motion quality of real `s02` and `s05` Gemini Omni clips. **Further coloring or adding polygon buildings will NOT be represented as closing the creative gap.** Existing CI success means an MP4 exists; `visual_quality_pass=null` and the Owner has not approved the style as a final ad.

One owner-locked creative destination remains: tiny canonical felt mascot traverses a genuine three-dimensional Auckland wool-diorama street network, cinematic zoom-in aerial→street, follow through supermarket/café/shopping, tired sheep goes home, camera zoom-out city→globe→unaltered official CityDiscount logo at ≥3.4s. Exact closing copy **都市折扣🌟，您的省钱助手小羊薅薅。**

## What can be reused without another model call

| Source | Nature | GitHub artifact ID | SHA256 of ORIGINAL 5s raw MP4 | New rev5 role |
|---|---|---|---|---|
| s02 | Real Omni original small character | `12339030552` | `a8a25ba43e5e8659d9c5528d685c69e8e0f991b990a48bf77c5c2be4fcfef80c` | Keep old real departure movement unless owner rejects |
| s05 | Real Omni original sheep digging, coin artwork incomplete | `12343403535` | `4ed60c4e769ab36e21186733931e89c23d1dcbb776e3274389216a2bb742fc56` | Keep existing real first dig (owner evaluate two distinct digs/coin) |
| s03 old | Real city-only environment from older concept | `12274786001` | `b718e6b0a6e5a64db66d74e6b1364326d16671823fca12935e8a3667b101af3f` | **Style/context reference only**; does not count as completed rev5 mascot shot |

These historical originals were independently re-downloaded and verified against their existing production receipt SHA hashes on **2026-10-22**; the user-facing owner-private evidence backup also contains the exact source artifact ZIPs, latest technical MP4 and contact sheet. All real source artifact ZIPs expire ~**Oct 28–29 NZDT**; safeguard separately before then.

`config/pilots/citydiscount_real_video_replacement_rev5.json` enumerates all **nine** unfulfilled character-performance shots (s01,s03,s04,s06,s07,s08,s09,s10,s11), each with a **separately ordered five-second prompt**, shared canonical look, exact timing, entry/exit geography and human QA criteria. This is a **nonexecutable planning/quality acceptance manifest**, not a hidden network action.

## Execute real model generation only after existing Owner Issue #188/#210 gates

Stage **G4**, Req **R4.4**, governance **AMEND-004/006**. The historical s02/s05 provider receipts note original-use rights assertions and transfer terms for **those previous runs**, but **they do not authorize any new transfer or new paid run**. Actual Google charges in original receipts are `null`/UNKNOWN and no independently matched October bill has been provided. We must not equate maximum operator reserve ($2) or model cost estimate with a paid invoice; Google provider has no guaranteed hard USD cap. Do not silently spend the AMEND-004 $5 NZ-day allowance based on missing actual charges.

Required decisions before even a first new real shot:

- Owner human confirms the original mascot image/viewpoint identity and rights for **specific source PNG hashes**, media uploaded to the exact chosen Google Gemini/Omni provider, retention/usage terms and whether any actor/family image reference may leave the repo (Owner Issue #210).
- Owner verifies actual prior model charges and remaining **NZ-day** spend via the Google billing ledger, confirms exact model/price/maximum provider exposure and isolated manual dispatch; never imply the repository can enforce actual provider spend cap.
- Owner explicitly authorizes the particular incremental first real run. Approval for production does NOT equal external publication. If budget+media permission not cleared, keep `can_trigger_model_run_now=false`.

Proposed economical order **after permission**: (A) adjacent **s03→s04** continuous volumetric town to supermarket, **s10→s11** small-lamb-to-home/crane-out route; (B) s06/s08 genuine felt travels; (C) s01/s07/s09 story beats. Validate each pair's last/first frames plus wool identity and actual costs **before** scaling to the other slots. No commercial call here and no vague promise that 3D world morph is solved: s12 globe remains hand-illustrated, not a true planet-render video.

The reusable offline ingestion and FFmpeg/technical QA already exist in `scripts/run_g4_existing_episode_offline.py`, `src/drama_factory/pipeline/existing_real_shots.py` and the rev5 review-cut process. **Do not build yet another ingestion, upload, retry, credential or DB framework**. Once approved real MP4s arrive, use existing ingestion with SHA/provenance and re-cut only the replaced slots; prefer matching the actual source's 360p/9:16 reference to 3:4 canvas **without stretch**.

**Reality gate:** `current_real_character_shots=2/11`, `old_s03_environment_only`, `s12=logo_endcard_not_real_earth`. Full rev5 **not** release-ready; G4 NOT_READY, G5 frozen; launch/publication requires Owner human creative approval.
