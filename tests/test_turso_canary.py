"""PR-30c: offline one-MP4 metadata canary, no secrets or paid services."""
from __future__ import annotations

import json
import os
import shutil
import sqlite3
from pathlib import Path

import pytest

from drama_factory.storage.drive_objects import FakeDriveClient, DriveArtifactError
from drama_factory.storage.turso_receipts import TursoMetadataTarget, TursoReceiptError
from drama_factory.storage.turso_canary import run_turso_canary, run_cli

FFMPEG = pytest.mark.skipif(
    not (shutil.which("ffmpeg") and shutil.which("ffprobe")),
    reason="Real FFmpeg test MP4 required; enforced in offline-video job",
)
REAL_TARGET = TursoMetadataTarget(
    url="libsql://ai-short-drama-factory-mrlukahuang.aws-ap-southeast-2.turso.io",
    engine="libsql",
)


def test_live_requires_all_confirmations_before_any_cloud_access(tmp_path, monkeypatch):
    for key in (
        "DRAMA_TURSO_CANARY_CONFIRM", "DRAMA_DRIVE_SMOKE_CONFIRM",
        "DRAMA_ENABLE_DRIVE_UPLOAD", "DRAMA_ENABLE_DRIVE_READ",
        "DRAMA_ENABLE_TURSO_METADATA_WRITE", "DRAMA_TURSO_WRITE_CONFIRM",
        "TURSO_AUTH_TOKEN", "DRAMA_DRIVE_USER_OAUTH_JSON",
    ):
        monkeypatch.delenv(key, raising=False)
    with pytest.raises(TursoReceiptError, match="confirmation"):
        run_turso_canary(
            tmp_path / "blocked", live=True,
            parent_folder_id="appFolder12345678", target=REAL_TARGET,
        )
    assert not (tmp_path / "blocked").exists()


def test_live_refuses_injected_fake_clients_and_wrong_engine(tmp_path, monkeypatch):
    with pytest.raises(TursoReceiptError, match="injected"):
        run_turso_canary(
            tmp_path / "blocked", live=True,
            parent_folder_id="appFolder12345678", target=REAL_TARGET,
            drive_client=FakeDriveClient(),
        )
    assert not (tmp_path / "blocked").exists()


@FFMPEG
def test_fake_one_mp4_creates_and_reads_single_remote_receipt(tmp_path, monkeypatch):
    # Even if a developer has real cloud creds in the environment, offline test
    # is isolated to FakeDrive + SQLite memory, never opens real network.
    import drama_factory.storage.turso_canary as canary

    monkeypatch.setattr(
        canary, "_open_remote",
        lambda *args, **kwargs: (_ for _ in ()).throw(
            AssertionError("Offline mode unexpectedly tried remote access")
        ),
    )
    fake = FakeDriveClient()
    result = run_turso_canary(tmp_path / "fake", drive_client=fake)
    assert result == {
        "mode": "fake", "engine": "libsql",
        "dedicated_name_validated": True,
        "drive_round_trip_verified": True,
        "uploaded_mp4_count": 1,
        "sha256_match": True,
        "size_bytes": result["size_bytes"],
        "turso_table": "drama_drive_receipts_v1",
        "turso_metadata_inserted": True,
        "turso_full_row_readback_verified": True,
        "database_modified": True,
        "remote_ids_redacted": True,
        "new_ai_model_generation_calls": 0,
        "production_sqlite_migrated": False,
    }
    assert result["size_bytes"] >= 1000
    assert fake.upload_calls == 1
    assert fake.download_calls == 2
    receipt = json.loads((tmp_path / "fake" / "turso-canary-verification.json").read_text())
    assert receipt == result
    serialized = json.dumps(receipt)
    assert "fakeVideo" not in serialized
    assert "fakeFolder" not in serialized
    assert "drivecopy" not in serialized
    assert "production_id" not in serialized


@FFMPEG
def test_corrupted_fake_drive_blocks_all_metadata_writes(tmp_path, monkeypatch):
    import drama_factory.storage.turso_canary as canary

    calls = []
    monkeypatch.setattr(
        canary, "mirror_verified_drive_receipt",
        lambda *args, **kwargs: calls.append("remote write"),
    )
    fake = FakeDriveClient()
    fake.corrupt_download = True
    with pytest.raises(DriveArtifactError, match="SHA256 mismatch"):
        run_turso_canary(tmp_path / "corrupt", drive_client=fake)
    assert fake.upload_calls == 1
    assert calls == []
    assert not (tmp_path / "corrupt" / "turso-canary-verification.json").exists()


@FFMPEG
def test_mocked_live_flow_pings_before_upload_and_mirrors_once(tmp_path, monkeypatch):
    import drama_factory.storage.turso_canary as canary
    import drama_factory.storage.drive_canary as drive_canary

    for key, value in {
        "DRAMA_TURSO_CANARY_CONFIRM": "UPLOAD_AND_MIRROR_ONE_VERIFIED_MP4",
        "DRAMA_DRIVE_SMOKE_CONFIRM": "UPLOAD_ONE_PRIVATE_TEST_MP4",
        "DRAMA_ENABLE_DRIVE_UPLOAD": "YES",
        "DRAMA_ENABLE_DRIVE_READ": "YES",
        "DRAMA_ENABLE_TURSO_METADATA_WRITE": "YES",
        "DRAMA_TURSO_WRITE_CONFIRM": "MIRROR_VERIFIED_DRIVE_METADATA",
        "TURSO_AUTH_TOKEN": "test-only-secret",
        "DRAMA_DRIVE_USER_OAUTH_JSON": '{"refresh_token":"test-only"}',
    }.items():
        monkeypatch.setenv(key, value)

    sql = sqlite3.connect(":memory:")
    calls = []
    class TracedConnection:
        def execute(self, stmt, params=()):
            calls.append(stmt)
            return sql.execute(stmt, params)
        def commit(self):
            return sql.commit()
        def rollback(self):
            return sql.rollback()
        def close(self):
            return sql.close()

    remote = TracedConnection()
    monkeypatch.setattr(canary, "_open_remote", lambda target, token: remote)
    original = drive_canary.run_drive_canary

    def simulate_cloud(output, *, live, parent_folder_id, on_verified):
        assert live is True
        assert parent_folder_id == "appFolder12345678"
        assert calls == ["SELECT 1"]  # SQL ping before any Drive activity
        return original(
            output, live=False, parent_folder_id="fakeDriveRoot0001",
            client=FakeDriveClient(), on_verified=on_verified,
        )

    monkeypatch.setattr(drive_canary, "run_drive_canary", simulate_cloud)
    result = run_turso_canary(
        tmp_path / "live-sim", live=True,
        parent_folder_id="appFolder12345678", target=REAL_TARGET,
    )
    assert result["mode"] == "live"
    assert result["drive_round_trip_verified"]
    assert result["turso_metadata_inserted"]
    assert result["turso_full_row_readback_verified"]
    assert sum("INSERT INTO drama_drive_receipts_v1" in s for s in calls) == 1
    assert sum("CREATE TABLE IF NOT EXISTS drama_drive_receipts_v1" in s for s in calls) == 1
    assert any("SELECT drive_copy_id" in s for s in calls)
    assert "test-only-secret" not in json.dumps(result)


def test_cli_redacts_all_dependency_errors(tmp_path, monkeypatch, capsys):
    import drama_factory.storage.turso_canary as canary

    def fail(*args, **kwargs):
        raise RuntimeError("SDK error bearer SUPER_SECRET_AND_DRIVE_OAUTH_VALUE")
    monkeypatch.setattr(canary, "run_turso_canary", fail)
    assert run_cli(["--out", str(tmp_path / "none")]) == 1
    captured = capsys.readouterr()
    assert captured.out == ""
    assert "SUPER_SECRET" not in captured.err
    assert "error details redacted" in captured.err
    assert "Traceback" not in captured.err


def test_manual_workflow_uses_explicit_gate_and_no_auto_uploads():
    root = Path(__file__).resolve().parents[1]
    yml = (root / ".github/workflows/manual-drive-turso-receipt-canary.yml").read_text()
    assert "workflow_dispatch:" in yml
    assert "pull_request:" not in yml
    assert "\n  push:" not in yml
    assert "contents: read" in yml
    assert "UPLOAD_AND_MIRROR_ONE_VERIFIED_MP4" in yml
    assert "inputs.confirmation == 'UPLOAD_AND_MIRROR_ONE_VERIFIED_MP4'" in yml
    assert "secrets.DRAMA_DRIVE_USER_OAUTH_JSON" in yml
    assert "secrets.DRAMA_DRIVE_PARENT_FOLDER_ID" in yml
    assert "secrets.DRAMA_TURSO_DATABASE_URL" in yml
    assert "secrets.DRAMA_TURSO_AUTH_TOKEN" in yml
    assert "DRAMA_FACTORY_OFFLINE: '1'" in yml
    assert "DRAMA_ENABLE_TURSO_METADATA_WRITE: 'YES'" in yml
    assert "DRAMA_TURSO_WRITE_CONFIRM: MIRROR_VERIFIED_DRIVE_METADATA" in yml
    assert "python -m pip install -e '.[test,drive-storage,turso-libsql]'" in yml
    assert "python -m drama_factory.storage.turso_canary --live" in yml
    assert "path: artifacts/pr30c-canary/turso-canary-verification.json" in yml
    assert "google-omni" not in yml
    assert "GEMINI_API_KEY" not in yml
