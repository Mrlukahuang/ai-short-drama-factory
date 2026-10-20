# CityDiscount Pilot 01 — Owner-selected v1 reference fixtures

The owner explicitly selected the **NEW revised mascot** already uploaded to this branch on 2026-10-20. **No additional upload is required.**

| Fixture | GitHub file | File size | Exact Git blob SHA-1 |
|---|---|---:|---|
| Canonical mascot v1 | `mascot_character_sheet_v1.png` | 2,211,254 bytes | `a5665b80a8484d5124fb874576ff40372f5a7c06` |
| Canonical CD logo v1 | `citydiscount_logo_v1.png` | 93,326 bytes | `903f96f235b5375fb540f3ad656ba39eea2b50e2` |

Logo source SHA256 is verified `19a6202331db9853d384ddabd30fbdf738f139fd8721638eed54fde193011651`. **Revised mascot source SHA256 is not yet known from a trusted binary readback**, since the available GitHub connector does not return the >1 MB PNG bytes. On trusted checkout, `scripts/citydiscount_pilot_preflight.py` computes its SHA256 from real bytes, checks exact Git blob SHA1, and refuses wrong variants. **Do not reuse old mascot SHA256 `79e653ff...`**; that belongs to the superseded 2,303,266-byte artwork. The new v1 must be visually reviewed before external model use.

These uploaded files are real Pilot 01 sample inputs for the **generic** `ai-short-drama-factory` pipeline. New requirement and generic adapter: [Issue #194](https://github.com/Mrlukahuang/ai-short-drama-factory/issues/194), [PR #195](https://github.com/Mrlukahuang/ai-short-drama-factory/pull/195). The pipeline must work unchanged for an unrelated cast/episode. Do not treat a CityDiscount-only static video or an 11-step receipt template as successful AI production.

Keep all `media_submission_allowed`, `operator_approved_for_model`, paid call, and publish states **false** until genuinely authorized. No extra brand image upload, new model run, merge or release is inferred by this fixture version selection.
