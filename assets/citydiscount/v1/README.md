# Pilot 01 — versioned reference image fixtures

Owner-confirmed 2026-10-20 **CityDiscount revised mascot V1** and **original CD flower logo V1**, copied into this branch by pointing directly to the **same Git blobs uploaded by the owner**. The bytes were not modified, compressed, redrawn or regenerated.

| Asset | Git object SHA-1 | Size |
|---|---|---:|
| `mascot_character_sheet_v1.png` | `a5665b80a8484d5124fb874576ff40372f5a7c06` | 2,211,254 |
| `citydiscount_logo_v1.png` | `903f96f235b5375fb540f3ad656ba39eea2b50e2` | 93,326 |

**The mascot is NOT the earlier 2,303,266-byte character sheet.** Do not pin the earlier SHA256 `79e653ff555185df85df52b642fa3a606f92b688a2b83b6cb15d8dc4521602cb` to this new source image.

The logo original SHA256 was previously checked: `19a6202331db9853d384ddabd30fbdf738f139fd8721638eed54fde193011651`. The revised mascot SHA256 must be computed from checked-out bytes before approving its use in a media request. `tests/test_g4_repository_asset_fixtures.py` checks both PNG files by actual checked-out bytes and Git blob digest.

**Purpose:** these are input fixtures to test the **existing reusable drama/video factory** asset intake → StoryBible → Screenplay → media references → VideoProvider → audio/FFmpeg/QA. No CityDiscount-only renderer, no production UI/service.

**Permission:** repository upload and use as local engineering test fixtures do not independently prove broad content rights or give permission to transfer image bytes to Google/other video models. Actual provider calls, fees, publication, and G4 graduation require separate checks/approvals. No release claims can be made from this directory.


## Operator-selected V1 camera and expression references (2026-10-20)

Ten original, distinct RGBA PNG files are now versioned under `character_views/`.
`character_views_inventory.json` pins exact SHA256, source dimensions and
role for each of four camera angles and six action/expression states.
`tests/test_g4_local_image_inventory.py` verifies checked-out **actual bytes**
against those pins, decodes each PNG, and validates its separate derived
RGB sanitized reference through the existing FND-02 media byte gate.

Source image SHA256 and normalized RGB PNG SHA256 are **different** digests;
neither is a signed legal rights declaration. Filenames and hashes do not
independently prove that a pose visually matches its declared angle, that
the pictures were cropped directly from the original sheet, or that an
external model may receive any media. Before real video calls, a trusted
operator must visually confirm view semantics, image rights, and obtain
the existing signed per-shot media authorization. No auto-grant in CI.
