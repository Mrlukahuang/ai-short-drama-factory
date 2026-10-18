# G4 / R4.4 / W2 — Deterministic per-shot asset bindings

Issue: https://github.com/Mrlukahuang/ai-short-drama-factory/issues/169

This is an **offline-only** manifest. It does not submit model calls, publish media, or alter historical 12-shot/W1 outputs. Base: main 409d042ae00e6d66fd097b86e0d34555eb20b83e.

## Existing code reused and reason for the thin adapter

- screenplay.py: Screenplay, DialogueCue and check_screenplay_scope check speaker and series/actor/scene integrity. No second global checker.
- screenplay_video_plan.py: build_screenplay_video_plan keeps the legacy request, contiguous selection, on-screen cast filters, original SHA and budget/publishing gates. Unchanged.
- models.py: ActorBible appearance, identity_anchors, costume_notes and optional voice_asset_id; SceneBible/VoiceBible, current story_bibles and series_assets DB tables.
- assets/references.py and shot_reference_board.py are metadata and local human reference records. Their model_use_approved=false cannot be converted into Omni media support.
- ViMax storyboard_artist.py / character_portraits_generator.py and Jellyfish shot_character_links.py / shot_assets.py / shot_video_readiness.py inspire explicit cast links and readiness checks, **design-only**, no upstream code copied. Fixed commits and license review are in docs/development_bible/OPEN_SOURCE_REUSE.md. No imported source/NOTICE change needed.

The missing capability is version-pin verification plus deterministic per-shot manifest. It is implemented as a single read-only adjacent module, src/drama_factory/pipeline/shot_asset_binding.py, with build_bound_screenplay_video_plan(db, screenplay, context, *, style_prompt, style_version, source_response_sha256, locked_assets, shot_ids=None, source_episode_report_sha256=None, shot_appearance_anchors=None). Caller supplies all exact asset IDs and {version, specification_sha256} for every referenced actor, scene and optional voice. The SHA is computed from the original UTF-8 series_assets.specification_json string, not a media file.

## Contract

Return: {manifest, manifest_sha256, plan}. Manifest schema is g4-shot-asset-binding.v1. Contains story_bible version/SHA, screenplay/source response/report SHA, style version/SHA and each shot's character_ids, actor ID/version/spec SHA/exact appearance/identity_anchors/costume_notes, scene ID/version/spec SHA, optional voice asset ID/version/SHA, speaker_actor_id, expected_dialogue and original cue timing.

Costume is part of the versioned ActorBible specification: costume_version_source=actor_asset_version. **There is no independent wardrobe version in the existing schema**, and W2 does not invent one. Missing costume notes fail closed. A spec SHA is an asset-metadata digest, never a claim that image/audio bytes exist or that the supplier consumed media.

Canonical JSON uses ensure_ascii=False, sort_keys=True, separators=(',', ':'). Rebuilding fixed inputs yields byte-identical canonical JSON and SHA. Any change in pinned versions/spec SHA, Story Bible, screenplay, style version or source SHA changes the downstream manifest SHA. Prior immutable manifest JSON can be retained as a historical record; the current DB alone cannot reconstruct a prior overwritten asset spec.

Every selected shot retains prior_prompt_sha256 (legacy existing planner) and gets a separate new prompt_sha256; the request_preview input is the new offline-only prompt with precisely the actors appearing in that shot. A versioned manifest does not rewrite the old prompt or receipt. Existing production_assets_verified=false and paid_execution_authorized=false remain false. Manifest reference_mode=prompt_anchor_only, provider_reference_applied=false, reference_images_supported=false, audio_reference_supported=false, publish_approved=false, new_paid_model_calls=0.

Fail closed for unknown/wrong-series actor, scene, voice, wrong kind, missing/incorrect version, empty/bad SHA, modified spec, missing actor appearance/identity/costume, mismatched per-shot appearance anchor, unlisted speaker or invalid cue. Validation already covered by Pydantic and check_screenplay_scope is reused rather than rewritten.

## Verification and provenance

Offline test: pytest -q tests/test_w2_shot_asset_binding.py tests/test_screenplay_video_plan.py tests/test_screenplay.py; plus all actual PR CI checks (scope/test). Synthetic 60-second screenplay from existing test_writer_execution_prep fixtures, with typed asset specifications inserted into temporary SQLite. W1's actual source response digest c5665e198eb3d30110a0bb6dc30d5f2cfadf74979eb5e6e0596d64751ff1a6f9 is recorded as a source identifier; it does **not** mean this test downloaded or replayed real 12-shot media.

The already verified real-media W1 receipt is docs/handoff/W1_EVIDENCE_20261019.md (Run39137352545, W1 Fake SHA de6d623523d8537461571b66508ee997a28e10fed23cd927900c3f8370a6df2f; original delivery SHA f76daf3065796ef847500041648f5dadb1cffa98898c466f11ac3471be9e8887). W2 does not modify its assets or invoices. Real model behavior, visual face consistency, voice, speech/lip-sync, content QA, human publication approval remain unverified.

## Next package input

Pass manifest + manifest_sha256 + per-shot old/new prompt SHA, pinned actor/scene/voice versions, exact dialogue, story/screenplay/source SHA and explicit unsupported provider-reference flags to W3/W4. No new API/paid calls or permission grants. Roll back by reverting W2 PR; existing W1/FFmpeg/provider paths are unaffected.
