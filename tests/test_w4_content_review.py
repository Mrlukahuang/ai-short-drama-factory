"""W4 regression contracts: receipt integrity, human attestation, unknown gates."""
import copy
import hashlib
import json

import pytest

from drama_factory.pipeline.content_review import (
    FIELDS, ContentReviewError, assess_bundle, load_w3_bundle, sign_review,
)


ORIGINAL_S07 = "ba02d9778df4fa78e436b104d7ac8a605db3b46d2a3dc06c2a8fa339350defc4"
S04 = "e2d31cdc7fa767a577eb9f5e623e855e71c5599877d502191aabc2a29ace0054"
S03 = "9bc4aefb7cb615a6146a0399d242060109ad8e19c720c4f8f81b76f837594ea0"
S09 = "108490fc1c441dec72fd006206a23089bdf965f47c397842e5af1176723f30f5"


def sha(payload):
    return hashlib.sha256(payload).hexdigest()


def save_json(path, data):
    path.write_text(json.dumps(data, ensure_ascii=False, sort_keys=True), encoding="utf-8")


def make_artifact(base, version="original", parent=None):
    base.mkdir()
    shots = []
    for i in range(12):
        sid = f"s{i + 1:02}"
        clip_sha = sha(sid.encode())
        if sid == "s03":
            clip_sha = S03
        elif sid == "s04":
            clip_sha = S04
        elif sid == "s07":
            clip_sha = ORIGINAL_S07 if version == "original" else S04
        elif sid == "s09":
            clip_sha = S09
        shots.append({"shot_id": sid, "clip_sha256": clip_sha,
                      "start_ms": 5013 * i, "end_ms": 5013 * (i + 1),
                      "duration_ms": 5013, "measured_duration_seconds": "5.013"})
    media = b"synthetic-W3-media-" + version.encode()
    (base / "gpt-episode-caption-draft.mp4").write_bytes(media)
    srt = b"1\n00:00:00,000 --> 00:00:01,000\nDRAFT\n"
    (base / "draft-captions.srt").write_bytes(srt)
    repair = {"replacement_mode": "original_completed_episode", "replacements": [],
              "parent_source_crosschecked": False}
    if version == "w1_fake":
        repair = {
            "replacement_mode": "operator_existing_media_offline_simulation",
            "parent_source_crosschecked": True,
            "parent_preview_sha256": parent["original_mp4_sha256"],
            "replacements": [{"shot_id": "s07", "old_sha256": ORIGINAL_S07,
                              "new_sha256": S04}],
        }
    render = {
        "contract": "g4-w3-render-provenance.v1", "step": "09_render",
        "shot_order": [f"s{i + 1:02}" for i in range(12)], "shots": shots,
        "measured_shot_total_ms": 60156, "mp4_sha256": sha(media),
        "original_mp4_sha256": "b" * 64,
        "source_response_sha256": "c" * 64, "original_source_report_sha256": "d" * 64,
        "srt_sha256": sha(srt), "subtitle_cues": 1,
        "subtitle_mode": "screenplay_timed_draft_not_asr",
        "asset_manifest_sha256": None, "production_assets_verified": False,
        "audio_stream_copy": True, "repair": repair,
    }
    save_json(base / "09_render.json", render)
    qa = {"step": "10_qa", "technical_decode_passed": True,
          "embedded_draft_subtitles_verified": True, "publish_approved": False,
          "dialogue_content_verified": False, "subtitle_alignment_verified": False,
          "mp4_sha256": sha(media), "subtitle_cue_count": 1,
          "source_response_sha256": "c" * 64, "original_source_report_sha256": "d" * 64,
          "render_receipt_sha256": sha((base / "09_render.json").read_bytes())}
    save_json(base / "10_qa.json", qa)
    return load_w3_bundle(base, artifact_id=101 if version == "original" else 102,
                          version=version, expected_mp4_sha256=sha(media), parent=parent)


def make_review(bundle, sid="s01", verdict="unknown", *, listened=True, watched=True):
    shot = bundle["shots"][int(sid[1:]) - 1]
    record = {
        "artifact_id": bundle["artifact_id"], "final_mp4_sha256": bundle["final_mp4_sha256"],
        "parent_final_mp4_sha256": bundle["parent_final_mp4_sha256"],
        "shot_id": sid, "shot_video_sha256": shot["clip_sha256"],
        "start_ms": shot["start_ms"], "end_ms": shot["end_ms"],
        "srt_sha256": bundle["srt_sha256"], "reviewer": "operator-one",
        "reviewed_at": "2026-10-19T00:00:00Z", "review_mode": "human_attested",
        "review_source": "local_media_manual",
        "evidence": {"note": "Operator viewed and listened to this source version",
                     "watched_video": watched, "listened_audio": listened},
        "verdicts": dict.fromkeys(FIELDS, verdict),
    }
    record["attestation_hmac_sha256"] = sign_review(record, b"local-secret")
    return record


def test_original_known_failures_and_no_fake_inheritance(tmp_path):
    original = make_artifact(tmp_path / "original")
    fake = make_artifact(tmp_path / "fake", "w1_fake", original)
    old_result = assess_bundle(original, [])
    fake_result = assess_bundle(fake, [])
    assert [x["shot_id"] for x in old_result["repair_suggestions"]] == ["s03", "s07", "s09"]
    assert [x["shot_id"] for x in fake_result["repair_suggestions"]] == ["s03", "s07", "s09"]
    assert "three_panel_split_screen" in old_result["shots"][6]["reason_codes"]
    assert "three_panel_split_screen" not in fake_result["shots"][6]["reason_codes"]
    assert "existing_s04_as_s07_fake_not_content_repair" in fake_result["shots"][6]["reason_codes"]
    assert fake_result["shots"][6]["checks"]["split_screen"] == "unknown"
    assert old_result["human_review_attested_count"] == fake_result["human_review_attested_count"] == 0
    assert all(x["checks"]["expected_vs_heard_dialogue"] == "unknown" for x in old_result["shots"])
    assert old_result["content_qa"] == "fail" and old_result["technical_qa"] == "pass"
    assert old_result["release_qa"] == "blocked" and old_result["publish_approved"] is False
    assert old_result["visual_auto_precheck_status"] == "not_run"
    assert old_result == assess_bundle(original, [])


@pytest.mark.parametrize("mutator", [
    lambda p: (p / "draft-captions.srt").write_text("bad subtitle"),
    lambda p: (p / "gpt-episode-caption-draft.mp4").write_bytes(b"tampered"),
    lambda p: (p / "09_render.json").write_text("{}"),
    lambda p: (p / "10_qa.json").write_text("{}"),
])
def test_tampered_evidence_rejected(tmp_path, mutator):
    root = tmp_path / "source"
    bundle = make_artifact(root)
    mutator(root)
    with pytest.raises(ContentReviewError):
        load_w3_bundle(root, artifact_id=101, version="original",
                       expected_mp4_sha256=bundle["final_mp4_sha256"])


@pytest.mark.parametrize("fault", ["duplicate", "timeline", "bad_clip", "srt_digest"])
def test_wrong_w3_receipt_content_rejected_even_when_receipt_rehashed(tmp_path, fault):
    root = tmp_path / "source"
    bundle = make_artifact(root)
    render = json.loads((root / "09_render.json").read_text())
    if fault == "duplicate":
        render["shots"][1]["shot_id"] = "s01"
    elif fault == "timeline":
        render["shots"][3]["end_ms"] += 1
    elif fault == "bad_clip":
        render["shots"][3]["clip_sha256"] = "NOT-A-SHA"
    else:
        render["srt_sha256"] = "f" * 64
    save_json(root / "09_render.json", render)
    qa = json.loads((root / "10_qa.json").read_text())
    qa["render_receipt_sha256"] = sha((root / "09_render.json").read_bytes())
    save_json(root / "10_qa.json", qa)
    with pytest.raises(ContentReviewError):
        load_w3_bundle(root, artifact_id=101, version="original",
                       expected_mp4_sha256=bundle["final_mp4_sha256"])


def test_fake_requires_proven_parent_and_unchanged_other_shots(tmp_path):
    original = make_artifact(tmp_path / "original")
    fake = make_artifact(tmp_path / "fake", "w1_fake", original)
    with pytest.raises(ContentReviewError):
        load_w3_bundle(tmp_path / "fake", artifact_id=102, version="w1_fake",
                       expected_mp4_sha256=fake["final_mp4_sha256"])
    wrong = copy.deepcopy(original)
    wrong["shots"][0]["clip_sha256"] = "f" * 64
    with pytest.raises(ContentReviewError):
        load_w3_bundle(tmp_path / "fake", artifact_id=102, version="w1_fake",
                       expected_mp4_sha256=fake["final_mp4_sha256"], parent=wrong)


def test_attested_review_version_pinned_and_no_stale_inheritance(tmp_path):
    original = make_artifact(tmp_path / "original")
    fake = make_artifact(tmp_path / "fake", "w1_fake", original)
    review = make_review(original)
    report = assess_bundle(original, [review], reviewer_keys={"operator-one": b"local-secret"})
    assert report["human_review_attested_count"] == 1
    assert report["shots"][0]["disposition"] == "unknown"
    with pytest.raises(ContentReviewError):
        assess_bundle(fake, [review], reviewer_keys={"operator-one": b"local-secret"})
    with pytest.raises(ContentReviewError):
        assess_bundle(original, [review, review], reviewer_keys={"operator-one": b"local-secret"})


def test_unsigned_forged_and_mismatched_human_attestations_fail_closed(tmp_path):
    original = make_artifact(tmp_path / "source")
    good = make_review(original, verdict="pass")
    for edit in ("signature", "reviewer", "timestamp", "sha", "no_key"):
        record = copy.deepcopy(good)
        if edit == "signature":
            record["attestation_hmac_sha256"] = "0" * 64
        if edit == "reviewer":
            record["reviewer"] = "someone-else"
        if edit == "timestamp":
            record["reviewed_at"] = "2026-10-19"
        if edit == "sha":
            record["shot_video_sha256"] = "f" * 64
        with pytest.raises(ContentReviewError):
            assess_bundle(original, [record],
                          reviewer_keys={} if edit == "no_key" else {"operator-one": b"local-secret"})


def test_video_audio_required_for_non_unknown_and_no_positive_historical_override(tmp_path):
    original = make_artifact(tmp_path / "source")
    no_audio = make_review(original, verdict="pass", listened=False)
    with pytest.raises(ContentReviewError):
        assess_bundle(original, [no_audio], reviewer_keys={"operator-one": b"local-secret"})
    no_video = make_review(original, verdict="pass", watched=False)
    with pytest.raises(ContentReviewError):
        assess_bundle(original, [no_video], reviewer_keys={"operator-one": b"local-secret"})
    prior_negative = make_review(original, sid="s03", verdict="pass")
    report = assess_bundle(original, [prior_negative],
                           reviewer_keys={"operator-one": b"local-secret"})
    assert report["shots"][2]["disposition"] == "needs_repair"
    assert report["shots"][2]["checks"]["appearance_age"] == "fail"


def test_hash_deterministic_and_all_unknown_not_counted_usable(tmp_path):
    original = make_artifact(tmp_path / "source")
    x = assess_bundle(original, [])
    y = assess_bundle(original, [])
    assert x["report_sha256"] == y["report_sha256"]
    assert x["usable_shot_count"] == 0
    assert x["unknown_shot_count"] == 9
    assert x["asr_status"] == "not_run"
    assert x["r4_3_exit_status"] == "pending"
