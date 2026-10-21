"""G4 one-command existing real-shot offline replay through original W3 + W4.

All video and declared receipts here are SYNTHETIC TEST DATA. Nothing proves
Google's authenticity or content quality; never contacts remote providers.
"""
from __future__ import annotations

import hashlib
import json
from pathlib import Path
import shutil
import subprocess
import sys

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
from run_g4_existing_episode_offline import G4ReplayDenied, main, run_existing_episode_preview
from test_offline_render import make_production
from test_g4_existing_real_shot_handoff import _candidate

ffmpeg_needed=pytest.mark.skipif(
    not shutil.which("ffmpeg") or not shutil.which("ffprobe"),
    reason="Real FFmpeg and ffprobe required",
)


def _shot_manifest(tmp_path:Path, shots):
    # Relative paths are anchored to this manifest's own directory; both
    # absolute input paths and manifest-local paths are supported.
    entries=[]
    for x in shots:
        entries.append({
            "shot_id":x["shot_id"],
            "media_path":x["media_path"].name,
            "receipt_path":x["receipt_path"].name,
            "expected_sha256":x["expected_sha256"],
        })
    file=tmp_path/"source-shots.json"
    file.write_text(json.dumps({
        "schema":"g4-existing-real-shot-inputs.v1","shots":entries,
    }),encoding="utf-8")
    return file


def _run(client,tmp_path,shots,*,allow=False):
    _,run=make_production(client)
    db=client.app.state.db
    project=db.one(
        """SELECT e.project_id FROM productions p JOIN episodes e
           ON e.id=p.episode_id WHERE p.id=?""",(run,),
    )["project_id"]
    manifest=_shot_manifest(tmp_path,shots)
    args=dict(database_path=db.path,series_id=project,production_id=run,
              shot_manifest_path=manifest,output_root=tmp_path/"out",
              allow_placeholders=allow)
    return db,run,project,args


@ffmpeg_needed
def test_one_command_requires_existing_approvals_then_reuses_W3_W4_with_no_model(client,tmp_path):
    source=_candidate(tmp_path,sid="shot-1")
    db,run,project,args=_run(client,tmp_path,[source],allow=True)
    with pytest.raises(G4ReplayDenied,match="both review gates"):
        run_existing_episode_preview(**args)
    assert not (tmp_path/"out").exists()
    assert client.post(f"/api/v1/productions/{run}/approve-script").status_code==200
    with pytest.raises(G4ReplayDenied,match="both review gates"):
        run_existing_episode_preview(**args)
    assert client.post(f"/api/v1/productions/{run}/approve-characters").status_code==200

    doc=run_existing_episode_preview(**args)
    assert doc["real_source_shot_ids"]==["shot-1"]
    assert doc["missing_real_shot_ids"]==["shot-2"]
    assert doc["has_placeholder_shots"] is True
    assert doc["original_W3_render_used"] is True
    assert doc["original_W4_technical_reinspection_used"] is True
    assert doc["new_model_calls"]==0
    assert doc["additional_provider_cost_usd"]=="0"
    assert doc["technical_decode_passed"] is True
    assert doc["human_content_review_status"]=="not_run"
    assert doc["actual_voice_quality_status"]=="unknown"
    assert doc["release_status"]=="blocked"
    assert doc["prior_real_provider_invoices_verified"] is False
    assert doc["provider_video_origin_independently_authenticated"] is False
    assert doc["publish_approved"] is False
    movie=tmp_path/"out"/project/run/"preview.mp4"
    receipt=movie.with_name("g4-existing-real-episode-replay.json")
    assert movie.is_file() and receipt.is_file()
    assert json.loads(receipt.read_text("utf-8"))==doc
    assert str(tmp_path) not in receipt.read_text("utf-8")
    repeated=run_existing_episode_preview(**args)
    assert repeated["cached_shot_count"]==2
    assert repeated["technical_mp4_sha256"]==doc["technical_mp4_sha256"]


@ffmpeg_needed
def test_default_full_scope_rejects_missing_real_shot_before_writes(client,tmp_path):
    source=_candidate(tmp_path,sid="shot-1")
    db,run,project,args=_run(client,tmp_path,[source])
    for step in ("approve-script","approve-characters"):
        assert client.post(f"/api/v1/productions/{run}/{step}").status_code==200
    with pytest.raises(ValueError,match="complete"):
        run_existing_episode_preview(**args)
    assert not (tmp_path/"out").exists()
    assert db.one("SELECT status FROM productions WHERE id=?",(run,))["status"]=="ready_for_video_generation"


@ffmpeg_needed
def test_full_existing_source_episode_true_W3_W4_then_replay_without_double_payment(
    client,tmp_path,
):
    s1=_candidate(tmp_path,sid="shot-1")
    s2=_candidate(tmp_path,sid="shot-2",receipt_source="source_mp4_sha256")
    db,run,project,args=_run(client,tmp_path,[s2,s1])
    for step in ("approve-script","approve-characters"):
        assert client.post(f"/api/v1/productions/{run}/{step}").status_code==200
    first=run_existing_episode_preview(**args)
    assert first["all_source_shots_supplied"] is True
    assert first["missing_real_shot_ids"]==[]
    assert first["real_source_shot_ids"]==["shot-1","shot-2"]
    assert first["has_placeholder_shots"] is False
    assert first["technical_decode_passed"] is True
    assert first["publish_approved"] is False
    assert first["g4_exit_approved"] is False
    assert first["new_model_calls"]==0
    second=run_existing_episode_preview(**args)
    assert second["cached_shot_count"]==2
    assert second["technical_mp4_sha256"]==first["technical_mp4_sha256"]
    assert second["new_model_calls"]==0


@ffmpeg_needed
def test_wrong_pin_or_explicit_foreign_id_rejects_before_render(client,tmp_path):
    shot=_candidate(tmp_path,sid="shot-1")
    db,run,project,args=_run(client,tmp_path,[shot],allow=True)
    for step in ("approve-script","approve-characters"):
        assert client.post(f"/api/v1/productions/{run}/{step}").status_code==200
    doc=json.loads(args["shot_manifest_path"].read_text("utf-8"))
    doc["shots"][0]["expected_sha256"]="f"*64
    args["shot_manifest_path"].write_text(json.dumps(doc),encoding="utf-8")
    with pytest.raises(ValueError,match="SHA"):
        run_existing_episode_preview(**args)
    assert not (tmp_path/"out").exists()
    args["series_id"]="proj_"+"0"*14
    with pytest.raises(G4ReplayDenied,match="match series"):
        run_existing_episode_preview(**args)


def test_malformed_private_path_and_wrong_contract_refused_without_model(client,tmp_path):
    file=tmp_path/"external.json"
    file.write_text(json.dumps({
        "schema":"g4-existing-real-shot-inputs.v1",
        "shots":[{"shot_id":"shot-1","media_path":"/abs/f.mp4",
                  "receipt_path":"/abs/x.json","expected_sha256":"f"*64,
                  "extra":"forbidden"}]}),encoding="utf-8")
    db,run,project,args=_run(client,tmp_path,[_candidate(tmp_path,sid="shot-1")] if shutil.which("ffmpeg") else [],allow=True) if shutil.which("ffmpeg") else (None,None,None,None)
    # No valid Source needed for direct manifest schema rejection.
    from run_g4_existing_episode_offline import _inputs
    with pytest.raises(G4ReplayDenied,match="fields"):
        _inputs(file)
    symlink=tmp_path/"linked.json"
    symlink.symlink_to(file)
    with pytest.raises(G4ReplayDenied,match="Linked"):
        _inputs(symlink)
    if args is not None:
        with pytest.raises(SystemExit) as blocked:
            main([
                "--database",str(db.path),"--production-id",run,
                "--series-id",project,"--shot-manifest",str(file),
                "--output-root",str(tmp_path/"block-output"),
            ])
        assert blocked.value.code == 2
