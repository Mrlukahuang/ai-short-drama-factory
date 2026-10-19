"""G4 FND-02/03 end-to-end offline tests; no API, no real uploaded media."""
from __future__ import annotations

import copy
import hashlib
from pathlib import Path

import pytest
from PIL import Image

from test_g4_visual_production_plan import _data
from drama_factory.pipeline.visual_production_plan import (
    build_visual_production_plan, impacted_shots,
)
from drama_factory.pipeline.visual_keyframe_graph import (
    FrameGraphError, build_keyframe_graph, shot_frame_entry,
)
from drama_factory.pipeline.visual_media_admission import (
    MediaAdmissionError, issue_operator_grant, verify_operator_grant, verify_png,
)
from drama_factory.pipeline.omni_media_envelope import (
    FakeOmniReferenceProvider, OmniMediaCapability, prepare_offline_omni_envelope,
)
from drama_factory.pipeline.visual_spine_offline import fake_episode_visual_replay


KEY = b"trusted-independent-local-operator-key-xxxxxxxx"


def _image(path: Path, seed: str) -> str:
    img = Image.new("RGB", (32, 32))
    salt = hashlib.sha256(seed.encode()).digest()
    for y in range(32):
        for x in range(32):
            img.putpixel((x,y), (
                (x * 19 + y * 11 + salt[0]) % 256,
                (y * 7 + x * 13 + salt[1]) % 256,
                (x * y + salt[2]) % 256,
            ))
    img.save(path, "PNG")
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _fixture(tmp_path):
    w2, specs, gallery = _data()
    paths = {}
    for row in gallery:
        name = row["asset_id"] + "_" + row["view"]
        path = tmp_path / (name + ".png")
        row["png_sha256"] = _image(path, name)
        paths[row["png_sha256"]] = path
    plan = build_visual_production_plan(w2, specs, gallery)
    return w2, specs, gallery, plan, paths


def _grant(plan, shot_id, *, graph=None, key=KEY):
    shot = next(s for s in plan["shots"] if s["shot_id"] == shot_id)
    shas = [x["image"]["png_sha256"] for x in shot["selected_references"]]
    if graph is not None:
        frame = shot_frame_entry(graph, shot_id)
        shas += [f["png_sha256"] for f in (
            frame["first_frame"], frame["last_frame"]) if f is not None]
    return issue_operator_grant(
        plan, shot_id, shas, reviewer="operator-human",
        expiry_epoch=2_000_000_000, signing_key=key,
    )


def _payload(f, shot_id="s01", *, graph=None, extra_paths=None,
             grant=None, **options):
    plan, paths = f[3], {**f[4], **(extra_paths or {})}
    shot = next(s for s in plan["shots"] if s["shot_id"] == shot_id)
    imgpaths = [paths[x["image"]["png_sha256"]] for x in shot["selected_references"]]
    frame = shot_frame_entry(graph, shot_id) if graph else {}
    first = (frame.get("first_frame") or {}).get("png_sha256")
    last = (frame.get("last_frame") or {}).get("png_sha256")
    return prepare_offline_omni_envelope(
        plan, shot_id, original_prompt="同一毛毡双人对话，动作连续。",
        reference_paths=imgpaths,
        operator_grant=grant or _grant(plan, shot_id, graph=graph),
        verification_key=KEY, frame_graph=graph,
        first_frame_path=paths.get(first), last_frame_path=paths.get(last),
        now_epoch=1_800_000_000, **options,
    )


def test_all_twelve_fake_requests_replay_and_no_network(tmp_path, monkeypatch):
    f=_fixture(tmp_path)
    plan=f[3]
    grants={s["shot_id"]: _grant(plan,s["shot_id"]) for s in plan["shots"]}
    prompts={s["shot_id"]: "中文叙事固定角色和场景。" for s in plan["shots"]}
    # Runtime may never try to access any network during the composed replay.
    import socket
    def _no_network(*a, **k):
        raise AssertionError("Network must not be opened")
    monkeypatch.setattr(socket.socket, "connect", _no_network)
    replay=fake_episode_visual_replay(
        f[0], f[1], f[2], prompts=prompts,
        image_paths_by_sha256=f[4], grants_by_shot=grants,
        operator_verification_key=KEY, now_epoch=1_800_000_000,
    )
    assert replay == fake_episode_visual_replay(
        f[0], f[1], f[2], prompts=prompts, image_paths_by_sha256=f[4],
        grants_by_shot=grants, operator_verification_key=KEY, now_epoch=1_800_000_000)
    assert replay["shot_count"] == 12
    assert replay["new_paid_model_calls"] == 0
    assert replay["provider_reference_applied"] is False
    assert replay["g4_content_pass"] is False
    assert replay["publish_approved"] is False
    assert all(s["fake_result"]["is_mock"] for s in replay["shots"])
    assert "data" not in str(replay)


def test_image_array_matches_order_and_role_labels(tmp_path):
    envelope = _payload(_fixture(tmp_path))
    obj=envelope.request_payload
    assert obj["model"] == "gemini-omni-1.1-flash"
    assert [x["type"] for x in obj["input"]] == ["image"] * 5 + ["text"]
    assert all(x["mime_type"] == "image/png" for x in obj["input"][:-1])
    assert "<IMAGE_REF_0>" in obj["input"][-1]["text"]
    assert "<IMAGE_REF_4>" in obj["input"][-1]["text"]
    assert [r["role"] for r in envelope.receipt["media"]] == [
        "actor", "actor", "scene", "prop", "prop"]
    assert envelope.receipt["provider_reference_applied"] is False
    assert envelope.receipt["model_submission_allowed"] is False
    assert envelope.receipt["model_calls"] == 0
    assert FakeOmniReferenceProvider().evaluate(envelope)["model_calls"] == 0
    assert "data" not in str(envelope.receipt)


def test_missing_real_images_and_tampering_fail_closed(tmp_path):
    f=_fixture(tmp_path)
    path=next(iter(f[4].values()))
    path.write_bytes(path.read_bytes()+b"tampered")
    with pytest.raises(MediaAdmissionError, match="differ"):
        _payload(f)
    f=_fixture(tmp_path)
    path=next(iter(f[4].values()))
    path.unlink()
    with pytest.raises(MediaAdmissionError):
        _payload(f)


def test_expired_foreign_wrong_order_and_tampered_grants(tmp_path):
    f=_fixture(tmp_path)
    plan=f[3]
    grant=_grant(plan,"s01")
    with pytest.raises(MediaAdmissionError,match="expired"):
        verify_operator_grant(
            plan,"s01",grant["media_sha256_ordered"],
            grant=grant,verification_key=KEY,now_epoch=2_000_000_001)
    with pytest.raises(MediaAdmissionError,match="scope"):
        verify_operator_grant(
            plan,"s01",list(reversed(grant["media_sha256_ordered"])),
            grant=grant,verification_key=KEY,now_epoch=1_800_000_000)
    with pytest.raises(MediaAdmissionError,match="signature"):
        _payload(f,grant={**grant,"signature":"0"*64})
    with pytest.raises(MediaAdmissionError):
        _payload(f,grant={**grant,"shot_id":"s03"})


def test_missing_unknown_permission_and_operator_key(tmp_path):
    f=_fixture(tmp_path)
    with pytest.raises(MediaAdmissionError):
        _payload(f,grant={})
    with pytest.raises(MediaAdmissionError):
        issue_operator_grant(f[3],"s01",["0"*64],
                             reviewer="human",expiry_epoch=2_000_000_000,
                             signing_key=b"weak")


def test_first_frame_inherits_only_approved_dependency_and_same_scene(tmp_path):
    f=_fixture(tmp_path)
    frame_path=tmp_path/"s01_last.png"
    frame_sha=_image(frame_path,"last-frame")
    approved=[dict(shot_id="s01",kind="last",scene_id="scene_cafe",
                   png_sha256=frame_sha,human_reviewed=True,reviewer="human")]
    graph=build_keyframe_graph(f[3],approved,first_frame_required=False)
    s02=shot_frame_entry(graph,"s02")
    assert s02["first_frame"]["png_sha256"] == frame_sha
    assert s02["inherited_from_shot_id"] == "s01"
    envelope=_payload(f,"s02",graph=graph,extra_paths={frame_sha:frame_path})
    assert envelope.receipt["media"][0]["role"] == "first_frame"
    assert envelope.receipt["media"][0]["source_shot_id"] == "s01"
    assert "<FIRST_FRAME>" in envelope.request_payload["input"][-1]["text"]
    assert "<IMAGE_REF_0>" in envelope.request_payload["input"][-1]["text"]
    assert len(envelope.request_payload["input"]) == 7


def test_missing_first_frame_blocks_when_requested(tmp_path):
    f=_fixture(tmp_path)
    graph=build_keyframe_graph(f[3],[],first_frame_required=True)
    with pytest.raises(FrameGraphError,match="first frame"):
        _payload(f,"s02",graph=graph)


def test_first_and_last_frame_media_and_signed_scope(tmp_path):
    f=_fixture(tmp_path)
    a,b=tmp_path/"first.png",tmp_path/"last.png"
    sha1=_image(a,"first");sha2=_image(b,"last")
    rows=[
        dict(shot_id="s01",kind=kind,scene_id="scene_cafe",
             png_sha256=sha,human_reviewed=True,reviewer="human")
        for kind,sha in (("first",sha1),("last",sha2))
    ]
    graph=build_keyframe_graph(f[3],rows,first_frame_required=False)
    envelope=_payload(f,"s01",graph=graph,extra_paths={sha1:a,sha2:b})
    assert [x["role"] for x in envelope.receipt["media"][:2]] == [
        "first_frame","last_frame"]
    assert len(envelope.request_payload["input"]) == 8
    with pytest.raises(MediaAdmissionError):
        _payload(f,"s01",graph=graph,extra_paths={sha1:a,sha2:b},
                 grant=_grant(f[3],"s01"))


def test_keyframe_duplicate_unapproved_cross_scene_rejected(tmp_path):
    f=_fixture(tmp_path)
    row=dict(shot_id="s01",kind="first",scene_id="scene_cafe",
             png_sha256="1"*64,human_reviewed=True,reviewer="human")
    for rows in ([row,row], [{**row,"scene_id":"elsewhere"}],
                 [{**row,"human_reviewed":False}]):
        with pytest.raises(FrameGraphError):
            build_keyframe_graph(f[3],rows)


def test_missing_media_in_future_dependencies_not_silently_used(tmp_path):
    f=_fixture(tmp_path)
    row=dict(shot_id="s09",kind="last",scene_id="scene_cafe",
             png_sha256="1"*64,human_reviewed=True,reviewer="human")
    graph=build_keyframe_graph(f[3],[row],first_frame_required=False)
    assert shot_frame_entry(graph,"s10")["first_frame"] is None
    assert impacted_shots(f[3],{"s02"}) == ["s02","s03","s04"]


def test_reference_capacity_prompt_collision_and_inline_byte_ceiling(tmp_path):
    f=_fixture(tmp_path)
    with pytest.raises(MediaAdmissionError,match="count"):
        _payload(f,capability=OmniMediaCapability(max_reference_images=4))
    with pytest.raises(MediaAdmissionError,match="too large"):
        _payload(f,capability=OmniMediaCapability(max_combined_inline_bytes=200))
    shot=f[3]["shots"][0]
    with pytest.raises(MediaAdmissionError,match="ambiguous"):
        prepare_offline_omni_envelope(
            f[3],"s01",original_prompt="<IMAGE_REF_0> hello",
            reference_paths=[f[4][x["image"]["png_sha256"]]
                             for x in shot["selected_references"]],
            operator_grant=_grant(f[3],"s01"),
            verification_key=KEY)


def test_keyframe_changes_receipt_but_not_historical_content(tmp_path):
    f=_fixture(tmp_path)
    base=_payload(f)
    other=_fixture(tmp_path)
    # Change an existing asset image and re-pin entire plan to new version.
    g=other[2]
    changed=next(r for r in g if r["asset_id"]=="cup")
    changed_path=tmp_path/"new_cup.png"
    changed["png_sha256"]=_image(changed_path,"new cup")
    new_plan=build_visual_production_plan(other[0],other[1],g)
    new_paths={**other[4],changed["png_sha256"]:changed_path}
    new_envelope=_payload((other[0],other[1],g,new_plan,new_paths))
    assert base.receipt["request_fingerprint_sha256"] != new_envelope.receipt["request_fingerprint_sha256"]
    assert base.receipt["model_calls"]==new_envelope.receipt["model_calls"]==0


def test_symlink_and_non_png_rejected(tmp_path):
    f=_fixture(tmp_path)
    real=next(iter(f[4].values()))
    link=tmp_path/"link.png"
    link.symlink_to(real)
    with pytest.raises(MediaAdmissionError):
        verify_png(link,hashlib.sha256(real.read_bytes()).hexdigest())
    fake=tmp_path/"fake.png"
    fake.write_bytes(b"i am not png" * 20)
    with pytest.raises(MediaAdmissionError,match="not a sanitized PNG"):
        verify_png(fake,hashlib.sha256(fake.read_bytes()).hexdigest())
