"""G4/R4.4: two separate reviewed stories -> W2 -> FND-01/02/03 -> Fake.

Entirely synthetic RGB media and an isolated test-only HMAC key. These tests
do not assert real image rights, review of Owner's lamb, or provider delivery.
"""
from __future__ import annotations

import copy
import json
import socket

import pytest

from drama_factory.pipeline.omni_media_envelope import FakeOmniReferenceProvider
from drama_factory.pipeline.screenplay_visual_bridge import plan_screenplay_visual_references
from drama_factory.pipeline.visual_keyframe_graph import build_keyframe_graph, shot_frame_entry
from drama_factory.pipeline.visual_media_admission import (
    MediaAdmissionError, issue_operator_grant,
)
from drama_factory.pipeline.visual_production_plan import VisualPlanError
from drama_factory.pipeline.visual_spine_offline import fake_episode_visual_replay
from test_g4_screenplay_visual_bridge import _inputs
from test_g4_visual_spine_full import _image


TEST_KEY = b"synthetic-offline-grant-key-not-a-real-approval-2026"


def _case(tmp_path, cast_count, shot_count, series_id):
    screenplay, manifest, gallery, views, props = _inputs(cast_count, shot_count)
    screenplay = screenplay.model_copy(update={"series_id": series_id})
    manifest["series_id"] = series_id
    for image in gallery:
        image["series_id"] = series_id

    shot_ids = manifest["selected_shot_ids"]
    shot_specs = {
        sid: {
            "actor_views": views[sid],
            "prop_pins": props[sid],
            "depends_on": [shot_ids[index - 1]] if index else [],
        }
        for index, sid in enumerate(shot_ids)
    }

    # All image bytes are generated from a fixture seed, not Owner media.
    folder = tmp_path / series_id
    folder.mkdir()
    paths = {}
    for row in gallery:
        label = f"{row['kind']}_{row['asset_id']}_{row['view']}"
        path = folder / (label + ".png")
        row["png_sha256"] = _image(path, series_id + label)
        paths[row["png_sha256"]] = path

    plan = plan_screenplay_visual_references(
        screenplay, manifest, gallery, actor_views=views, prop_pins=props,
    )
    # The FND-03 last frame of s01 may become the same-scene first frame of s02.
    last_path = folder / "s01_last.png"
    last_sha = _image(last_path, series_id + "-last-frame")
    paths[last_sha] = last_path
    reviewed_frames = [{
        "shot_id": "s01",
        "kind": "last",
        "scene_id": manifest["shots"][0]["scene_id"],
        "png_sha256": last_sha,
        "human_reviewed": True,
        "reviewer": "SYNTHETIC_TEST_ONLY",
    }]
    graph = build_keyframe_graph(plan, reviewed_frames, first_frame_required=False)
    grants = {}
    for shot in plan["shots"]:
        sid = shot["shot_id"]
        shas = [ref["image"]["png_sha256"] for ref in shot["selected_references"]]
        frame = shot_frame_entry(graph, sid)
        shas += [entry["png_sha256"] for entry in (
            frame["first_frame"], frame["last_frame"]) if entry is not None]
        grants[sid] = issue_operator_grant(
            plan, sid, shas, reviewer="SYNTHETIC_TEST_ONLY",
            expiry_epoch=2_000_000_000, signing_key=TEST_KEY,
        )
    return dict(
        reviewed_screenplay=screenplay, w2_manifest=manifest,
        shot_specs=shot_specs, gallery=gallery,
        prompts={sid: "Synthetic dialogue and fixed scene." for sid in shot_ids},
        image_paths_by_sha256=paths, grants_by_shot=grants,
        operator_verification_key=TEST_KEY, approved_frames=reviewed_frames,
        first_frame_required=False, now_epoch=1_800_000_000,
    )


def _replay(kwargs):
    return fake_episode_visual_replay(**kwargs)


def test_two_distinct_series_reach_fake_provider_without_network(tmp_path, monkeypatch):
    a = _case(tmp_path, 1, 12, "proj_00000000000001")
    b = _case(tmp_path, 2, 6, "proj_00000000000002")
    def block_network(*args, **kwargs):
        raise AssertionError("Offline integration must not open a network connection")
    monkeypatch.setattr(socket.socket, "connect", block_network)
    first = _replay(a)
    second = _replay(b)
    assert first["shot_count"] == 12 and second["shot_count"] == 6
    assert first["visual_plan_sha256"] != second["visual_plan_sha256"]
    assert first["keyframe_graph_sha256"] != second["keyframe_graph_sha256"]
    for data, expected in ((first, 12), (second, 6)):
        assert data["shot_count"] == expected
        assert data["new_paid_model_calls"] == 0
        assert data["actual_fee_usd"] is None
        assert data["real_video_generated"] is False
        assert data["provider_reference_applied"] is False
        assert data["g4_content_pass"] is False
        assert data["publish_approved"] is False
        assert all(row["fake_result"]["is_mock"] for row in data["shots"])
        assert '"data":' not in json.dumps(data)
        assert "SYNTHETIC_TEST_ONLY" not in json.dumps(data)
    # An explicitly declared dependency inherits the previous reviewed end frame.
    assert first["shots"][0]["request"]["media"][-1]["role"] == "last_frame"
    assert first["shots"][1]["request"]["media"][0]["role"] == "first_frame"
    assert first == _replay(a) and second == _replay(b)


def test_reviewed_screenplay_rejects_missing_shots_and_rewired_dependencies(tmp_path):
    data = _case(tmp_path, 1, 12, "proj_00000000000001")
    missing = copy.deepcopy(data)
    missing["w2_manifest"]["shots"].pop()
    missing["w2_manifest"]["selected_shot_ids"].pop()
    missing["shot_specs"].pop("s12")
    missing["prompts"].pop("s12")
    missing["grants_by_shot"].pop("s12")
    with pytest.raises(MediaAdmissionError, match="Reviewed screenplay shot scope"):
        _replay(missing)

    rewired = copy.deepcopy(data)
    rewired["shot_specs"]["s02"]["depends_on"] = []
    with pytest.raises(MediaAdmissionError, match="continuity"):
        _replay(rewired)


def test_reviewed_screenplay_rejects_swapped_cast_and_foreign_gallery(tmp_path):
    a = _case(tmp_path, 1, 12, "proj_00000000000001")
    b = _case(tmp_path, 2, 6, "proj_00000000000002")
    swapped = copy.deepcopy(b)
    swapped["w2_manifest"]["shots"][0]["character_ids"] = ["actor_b", "actor_a"]
    swapped["w2_manifest"]["shots"][0]["characters"].reverse()
    with pytest.raises(VisualPlanError, match="cast"):
        _replay(swapped)

    foreign = copy.deepcopy(a)
    foreign["gallery"] = b["gallery"]
    with pytest.raises(VisualPlanError, match="unapproved"):
        _replay(foreign)


def test_wrong_series_grant_and_tampered_png_fail_closed(tmp_path):
    a = _case(tmp_path, 1, 12, "proj_00000000000001")
    b = _case(tmp_path, 2, 6, "proj_00000000000002")
    wrong_grant = dict(a)
    wrong_grant["grants_by_shot"] = {**a["grants_by_shot"], "s01": b["grants_by_shot"]["s01"]}
    with pytest.raises(MediaAdmissionError, match="grant"):
        _replay(wrong_grant)

    # Local verified RGB media is never accepted with altered bytes.
    path = next(iter(a["image_paths_by_sha256"].values()))
    path.write_bytes(path.read_bytes() + b"tampered")
    with pytest.raises(MediaAdmissionError, match="differ"):
        _replay(a)
