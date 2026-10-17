# GPT screenplay development baseline (G4/R4.1)

Owner chose to proceed with GPT on 2026-10-18 NZT. Sol is the temporary development baseline, Luna remains an accepted import format. This is not a formal main/backup selection or a creative-quality winner. Gemini HTTP400 investigation does not block this offline import path.

## Reuse existing generated output

POST `/api/v1/series/{series_id}/screenplays/from-openai-response/validate` with:

```json
{
  "model": "gpt-6.1-sol",
  "request": {"story_bible_id": "existing-bible-id", "episode_number": 1,
    "target_duration_seconds": 60, "creative_brief": "原创分集简报",
    "actor_asset_ids": ["existing-lead-a", "existing-lead-b"],
    "scene_asset_id": "existing-scene-id", "prompt_version": "episode-drama-beats.zh.v1"},
  "response_date": "2026-10-17",
  "response": {"id": "replace-with-complete-supplied-Responses-JSON"}
}
```

The response placeholder above is NOT a valid model response; supply the complete already-generated Responses JSON. No API secret is an input. This route reconstructs the validation context from the existing series Bible, parses the supplied response, checks screenplay asset scope and returns screenplay + EpisodeDraft preview. It performs no network calls, database writes, model generation or approvals. Invalid/refused/truncated/model-mismatched responses are rejected.

Imported JSON is operator-supplied, not authenticated provider evidence. Reconstructed request hashes do not prove what was originally sent. Token usage may remain unknown; cost stays null pending cache-aware pricing and actual invoice checks. The known old parser estimate is intentionally not propagated.

Human review: inspect/edit returned screenplay; use existing `/screenplays/validate` after edits, then explicitly POST `/screenplays/commit` with `screenplay` and `reviewed_by_operator: true`. Commit creates one draft episode only. Production approvals remain separate; no video is generated. Import never supplies a true review flag.

Original comparison outputs use fixture IDs (comparison-fixture / comparison-bible / a-jie / xiao-yu / cafe). They cannot be imported into an unrelated series by changing the URL; no automatic ID remapping or asset creation is performed. Use matching existing assets/context or explicitly review a correctly scoped screenplay.

## Evidence

- Original run39035812309 / artifact12102675304: Sol and Luna completed; Flash400. Both GPT responses re-parsed locally through this module: Sol12 shots/60s, Luna8 shots/60s, pending review. This is reuse, not new generation or creative-quality approval.
- 96 related offline tests passed, including real SQLite + in-process FastAPI review/commit tests with synthetic responses. Full repository checks are recorded on the PR.
- First3 one-time claim remains consumed. No automatic repeats, no remaining15 launch, no new paid-call entry point. Fake outline endpoints and formal registry remain unchanged.
