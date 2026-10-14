"""Per-shot director image selections: precise draft+asset version, never approvals."""
from __future__ import annotations

import ast
from copy import deepcopy
from pathlib import Path

from PIL import Image
import pytest

from drama_factory.pipeline.local_asset_references import (
    stage_local_asset_reference,
)
from drama_factory.pipeline.local_story_workflow import (
    canonical_screenplay_digest, make_storyboard_template,
)
from drama_factory.pipeline.shot_reference_board import (
    LocalShotReferenceError, build_shot_reference_board,
    save_shot_reference_selection,
)
from test_local_asset_references import sample_image
from test_screenplay import setup_series


def setup(client, tmp_path):
    sid, bible, actor, scene = setup_series(client, "Director shot references")
    draft = make_storyboard_template(
        sid, bible, [actor], scene, shot_count=3, seconds_per_shot=4,
    )
    db = client.app.state.db
    gallery = tmp_path / "asset-references"
    binding = tmp_path / "shot-bindings"
    return db, sid, actor, scene, draft, gallery, binding


def store(db, sid, aid, root, color):
    return stage_local_asset_reference(
        db, sid, aid, root, filename="original.png",
        content=sample_image(color=color), operator_attests_rights=True,
    )["source_sha256"]


def select(db, draft, shot, choices, gallery, binding, confirm=True):
    return save_shot_reference_selection(
        db, draft, shot, choices, gallery, binding,
        operator_confirmed=confirm,
    )


def test_pinned_shot_selection_readback_is_human_only_and_shows_real_png(client, tmp_path):
    db, sid, actor, scene, draft, gallery, binding = setup(client, tmp_path)
    actor_ref = store(db, sid, actor, gallery, (25, 180, 95))
    scene_ref = store(db, sid, scene, gallery, (90, 30, 185))
    original_draft = deepcopy(draft)
    saved = select(db, draft, "S001", {actor: actor_ref, scene: scene_ref}, gallery, binding)
    assert saved["human_choice_recorded"] is True
    assert saved["selection_count"] == 2
    assert saved["model_use_approved"] is False
    assert saved["publication_approved"] is False
    assert saved["paid_api_calls"] == 0
    board = build_shot_reference_board(db, draft, gallery, binding)
    assert board["screenplay_fingerprint"] == canonical_screenplay_digest(draft)
    assert board["approval_granted"] is False and board["review_required"] is True
    assert board["model_use_approved"] is False and board["publication_approved"] is False
    assert [s["shot_id"] for s in board["shots"]] == ["S001", "S002", "S003"]
    imgs = board["shots"][0]["reference_images"]
    assert [(i["asset_id"], i["source_sha256"]) for i in imgs] == sorted([
        (actor, actor_ref), (scene, scene_ref),
    ])
    for img in imgs:
        assert img["png_bytes"].startswith(b"\x89PNG\r\n\x1a\n")
        assert img["rights_independently_verified"] is False
    assert len(board["shots"][1]["reference_images"]) == 0
    assert len(board["review_prompts"]) == 2
    assert set(i["kind"] for i in board["review_prompts"]) == {"missing_reference"}
    assert draft == original_draft
    assert client.get(f"/api/v1/projects/{sid}/episodes").json() == []


def test_adjacent_same_asset_different_reference_warns_without_auto_correction(client, tmp_path):
    db, sid, actor, scene, draft, gallery, binding = setup(client, tmp_path)
    first = store(db, sid, actor, gallery, (20, 40, 60))
    second = store(db, sid, actor, gallery, (55, 65, 75))
    select(db, draft, "S001", {actor: first}, gallery, binding)
    select(db, draft, "S002", {actor: second}, gallery, binding)
    issue = build_shot_reference_board(db, draft, gallery, binding)["review_prompts"]
    assert [(i["kind"], i["from_shot"], i["to_shot"]) for i in issue] == [
        ("different_reference", "S001", "S002"),
        ("missing_reference", "S002", "S003"),
    ]
    select(db, draft, "S002", {actor: first}, gallery, binding)
    issue2 = build_shot_reference_board(db, draft, gallery, binding)["review_prompts"]
    assert [i["kind"] for i in issue2] == ["missing_reference"]
    assert not (binding / sid / canonical_screenplay_digest(draft) / "S001.json").exists()


def test_new_draft_never_inherits_previous_shot_bindings(client, tmp_path):
    db, sid, actor, _, draft, gallery, binding = setup(client, tmp_path)
    ref = store(db, sid, actor, gallery, (15, 25, 35))
    select(db, draft, "S001", {actor: ref}, gallery, binding)
    revised = deepcopy(draft)
    revised["shots"][0]["action"] = "修改之后所有本地参考选择必须重新确认"
    old = build_shot_reference_board(db, draft, gallery, binding)
    new = build_shot_reference_board(db, revised, gallery, binding)
    assert old["screenplay_fingerprint"] != new["screenplay_fingerprint"]
    assert old["shots"][0]["explicitly_selected"] is True
    assert new["shots"][0]["reference_images"] == []
    select(db, revised, "S001", {actor: ref}, gallery, binding)
    assert build_shot_reference_board(db, draft, gallery, binding)["shots"][0]["explicitly_selected"]


def test_explicit_clear_and_idempotent_save(client, tmp_path):
    db, sid, actor, _, draft, gallery, binding = setup(client, tmp_path)
    ref = store(db, sid, actor, gallery, (11, 81, 190))
    x = select(db, draft, "S001", {actor: ref}, gallery, binding)
    y = select(db, draft, "S001", {actor: ref}, gallery, binding)
    assert x == y
    clear = select(db, draft, "S001", {}, gallery, binding)
    assert clear["selection_count"] == 0
    board = build_shot_reference_board(db, draft, gallery, binding)
    assert board["shots"][0]["explicitly_selected"] is False
    assert board["review_prompts"] == []


def test_prop_reference_is_local_annotation_and_cross_shot_reviewable(client, tmp_path):
    db, sid, actor, _, draft, gallery, binding = setup(client, tmp_path)
    result = client.post(f"/api/v1/series/{sid}/assets", json={
        "kind": "prop", "key": "red-scarf",
        "specification": {"name": "红围巾", "description": "原创红围巾道具"},
    })
    assert result.status_code == 201
    prop = result.json()["asset_id"]
    img = store(db, sid, prop, gallery, (185, 5, 10))
    select(db, draft, "S001", {prop: img}, gallery, binding)
    board = build_shot_reference_board(db, draft, gallery, binding)
    assert board["shots"][0]["reference_images"][0]["asset_kind"] == "prop"
    assert board["review_prompts"][0]["kind"] == "missing_reference"
    assert board["approval_granted"] is False
    assert draft["shots"][0].get("prop_ids") is None


def test_cross_series_invalid_cast_scene_voice_or_missing_reference_fail_closed(client, tmp_path):
    db, sid, actor, scene, draft, gallery, binding = setup(client, tmp_path)
    foreign_sid, _, foreign_actor, _ = setup_series(client, "Foreign")
    foreign_img = store(db, foreign_sid, foreign_actor, gallery, (3, 4, 5))
    valid_img = store(db, sid, actor, gallery, (12, 14, 16))
    voice = client.post(f"/api/v1/series/{sid}/assets", json={
        "kind": "voice", "key": "source-voice",
        "specification": {"name": "声音", "voice_description": "低频"},
    }).json()["asset_id"]
    with pytest.raises(LocalShotReferenceError, match="Foreign|Selected|incompatible"):
        select(db, draft, "S001", {foreign_actor: foreign_img}, gallery, binding)
    with pytest.raises(LocalShotReferenceError, match="incompatible"):
        select(db, draft, "S001", {voice: valid_img}, gallery, binding)
    with pytest.raises(LocalShotReferenceError, match="not available"):
        select(db, draft, "S001", {scene: valid_img}, gallery, binding)
    with pytest.raises(LocalShotReferenceError, match="not available"):
        select(db, draft, "S001", {actor: "0" * 64}, gallery, binding)
    with pytest.raises(LocalShotReferenceError, match="Unknown shot"):
        select(db, draft, "NONEXISTENT", {actor: valid_img}, gallery, binding)
    with pytest.raises(LocalShotReferenceError, match="confirmation"):
        select(db, draft, "S001", {actor: valid_img}, gallery, binding, confirm=False)
    assert not binding.exists()


def test_foreign_screenplay_bible_and_forged_asset_references_denied(client, tmp_path):
    db, sid, actor, scene, draft, gallery, binding = setup(client, tmp_path)
    _, bible2, actor2, scene2 = setup_series(client, "Other book")
    changed = deepcopy(draft)
    changed["story_bible_id"] = bible2
    with pytest.raises(LocalShotReferenceError, match="foreign"):
        build_shot_reference_board(db, changed, gallery, binding)
    changed = deepcopy(draft)
    changed["shots"][0]["character_ids"] = [actor2]
    with pytest.raises(LocalShotReferenceError, match="foreign"):
        build_shot_reference_board(db, changed, gallery, binding)
    changed = deepcopy(draft)
    changed["shots"][0]["scene_id"] = scene2
    with pytest.raises(LocalShotReferenceError, match="foreign"):
        build_shot_reference_board(db, changed, gallery, binding)


def test_stored_receipt_and_image_tampering_blocks_all_readback(client, tmp_path):
    db, sid, actor, _, draft, gallery, binding = setup(client, tmp_path)
    h = store(db, sid, actor, gallery, (80, 90, 100))
    select(db, draft, "S001", {actor: h}, gallery, binding)
    stored = next((binding / sid / canonical_screenplay_digest(draft)).glob("*.json"))
    original = stored.read_bytes()
    try:
        bad = original.replace(b'"model_use_approved": false', b'"model_use_approved": true')
        stored.write_bytes(bad)
        with pytest.raises(LocalShotReferenceError, match="scope"):
            build_shot_reference_board(db, draft, gallery, binding)
    finally:
        stored.write_bytes(original)
    img = gallery / sid / actor / (h + ".png")
    pristine = img.read_bytes()
    img.write_bytes(b"damaged")
    try:
        with pytest.raises(LocalShotReferenceError, match="verification"):
            build_shot_reference_board(db, draft, gallery, binding)
    finally:
        img.write_bytes(pristine)
    assert len(build_shot_reference_board(db, draft, gallery, binding)["shots"][0]["reference_images"]) == 1


def test_symlinked_folder_and_receipt_do_not_follow_files(client, tmp_path):
    db, sid, actor, _, draft, gallery, binding = setup(client, tmp_path)
    h = store(db, sid, actor, gallery, (120, 90, 60))
    select(db, draft, "S001", {actor: h}, gallery, binding)
    folder = binding / sid / canonical_screenplay_digest(draft)
    receipt = next(folder.glob("*.json"))
    old = receipt.with_suffix(".backup")
    receipt.rename(old)
    try:
        receipt.symlink_to(old)
        with pytest.raises(LocalShotReferenceError, match="scope"):
            build_shot_reference_board(db, draft, gallery, binding)
        with pytest.raises(LocalShotReferenceError, match="Linked"):
            select(db, draft, "S001", {actor: h}, gallery, binding)
    finally:
        receipt.unlink()
        old.rename(receipt)
    link = tmp_path / "link-root"
    link.symlink_to(binding, target_is_directory=True)
    with pytest.raises(LocalShotReferenceError, match="Linked"):
        build_shot_reference_board(db, draft, gallery, link)


def test_frontend_shot_reference_board_parses_without_streamlit_installed():
    root = Path(__file__).resolve().parents[1] / "frontend"
    for item in ("shot_reference_board.py", "app.py"):
        ast.parse((root / item).read_text(encoding="utf-8"), filename=str(item))
