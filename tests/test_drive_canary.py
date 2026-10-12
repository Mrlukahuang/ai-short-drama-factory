"""Local OAuth and no-network Google Drive canary tests."""
import json
import os
import shutil
from pathlib import Path

import pytest

from drama_factory.storage.drive_authorize import authorize_drive, FOLDER_NAME
from drama_factory.storage.drive_canary import run_drive_canary
from drama_factory.storage.drive_objects import DRIVE_FILE_SCOPE, DriveArtifactError, FakeDriveClient


class Credentials:
    refresh_token = "super_private_refresh"
    def to_json(self):
        return json.dumps({"refresh_token":self.refresh_token,"client_id":"private_id","client_secret":"private_secret"})


class Flow:
    def run_local_server(self, **kwargs):
        assert kwargs["access_type"] == "offline"
        assert kwargs["prompt"] == "consent"
        return Credentials()


class DriveService:
    def __init__(self, existing=False, duplicate=False):
        self.folders = ([{"id":"appFolder12345678","name":FOLDER_NAME,
                         "mimeType":"application/vnd.google-apps.folder"}]
                        if existing else [])
        if duplicate:
            self.folders *= 2
        self.created = 0
    def files(self):
        return self
    def list(self, **kwargs):
        assert "'root' in parents" in kwargs["q"]
        self.op = "list"
        return self
    def create(self, **kwargs):
        assert kwargs["body"]["name"] == FOLDER_NAME
        assert "parents" not in kwargs["body"]
        self.created += 1
        self.folders = [{"id":"appFolder12345678","name":FOLDER_NAME,
                         "mimeType":"application/vnd.google-apps.folder"}]
        self.op = "create"
        return self
    def execute(self):
        return {"files":list(self.folders)} if self.op == "list" else dict(self.folders[0])


def test_local_oauth_stores_private_token_and_creates_app_folder(tmp_path, capsys):
    client_file = tmp_path / "desktop-client.json"
    client_file.write_text("{}")
    service = DriveService()
    def get_flow(path, *, scopes):
        assert Path(path) == client_file
        assert scopes == [DRIVE_FILE_SCOPE]
        return Flow()
    record = authorize_drive(
        client_file, tmp_path / "config" / "oauth.json", flow_factory=get_flow,
        service_factory=lambda *a, **kw:service,
    )
    assert record["folder_id"] == "appFolder12345678" and service.created == 1
    token = tmp_path / "config" / "oauth.json"
    assert token.stat().st_mode & 0o077 == 0
    assert json.loads(token.read_text())["refresh_token"] == "super_private_refresh"
    assert "super_private_refresh" not in capsys.readouterr().out
    with pytest.raises(DriveArtifactError, match="exists"):
        authorize_drive(client_file, token, flow_factory=get_flow,
                        service_factory=lambda *a, **kw:service)


def test_reuses_app_folder_but_ambiguous_folder_fails_closed(tmp_path):
    client_file = tmp_path / "desktop.json"
    client_file.write_text("{}")
    service = DriveService(existing=True)
    get_flow = lambda *a,**kw: Flow()
    get_service = lambda *a,**kw: service
    out = tmp_path / "new" / "token.json"
    assert authorize_drive(client_file, out,flow_factory=get_flow,
                           service_factory=get_service)["folder_id"] == "appFolder12345678"
    assert service.created == 0
    duplicate = DriveService(existing=True, duplicate=True)
    blocked = tmp_path / "blocked.json"
    with pytest.raises(DriveArtifactError, match="Ambiguous"):
        authorize_drive(client_file,blocked,flow_factory=get_flow,
                        service_factory=lambda *a,**kw:duplicate)
    assert not blocked.exists()


def test_no_live_drive_access_without_all_gates(tmp_path, monkeypatch):
    fake = FakeDriveClient()
    output = tmp_path / "blocked"
    for key in ("DRAMA_ENABLE_DRIVE_UPLOAD", "DRAMA_ENABLE_DRIVE_READ",
                "DRAMA_DRIVE_SMOKE_CONFIRM"):
        monkeypatch.delenv(key, raising=False)
    with pytest.raises(DriveArtifactError, match="confirmation"):
        run_drive_canary(output,live=True,
                         parent_folder_id="appFolder12345678",client=fake)
    monkeypatch.setenv("DRAMA_DRIVE_SMOKE_CONFIRM","UPLOAD_ONE_PRIVATE_TEST_MP4")
    with pytest.raises(DriveArtifactError, match="gates"):
        run_drive_canary(output,live=True,
                         parent_folder_id="appFolder12345678",client=fake)
    assert fake.upload_calls == 0 and fake.download_calls == 0
    assert not output.exists()


def test_fake_mode_rejects_real_client_and_live_mode_refuses_mock_root(tmp_path,monkeypatch):
    with pytest.raises(DriveArtifactError,match="Fake mode"):
        run_drive_canary(tmp_path / "bad",client=object())
    monkeypatch.setenv("DRAMA_DRIVE_SMOKE_CONFIRM","UPLOAD_ONE_PRIVATE_TEST_MP4")
    monkeypatch.setenv("DRAMA_ENABLE_DRIVE_UPLOAD","YES")
    monkeypatch.setenv("DRAMA_ENABLE_DRIVE_READ","YES")
    with pytest.raises(DriveArtifactError,match="real app-created"):
        run_drive_canary(tmp_path / "bad",live=True,client=FakeDriveClient())
    assert not (tmp_path / "bad").exists()


@pytest.mark.skipif(not (shutil.which("ffmpeg") and shutil.which("ffprobe")),
                    reason="FFmpeg needed for genuine video verification")
def test_fake_canary_real_mp4_round_trip_and_safe_report(tmp_path,monkeypatch):
    monkeypatch.delenv("DRAMA_ENABLE_DRIVE_UPLOAD",raising=False)
    monkeypatch.delenv("DRAMA_ENABLE_DRIVE_READ",raising=False)
    fake = FakeDriveClient()
    result = run_drive_canary(tmp_path / "canary",client=fake)
    assert result["mode"] == "fake"
    assert result["verified"] is True
    assert result["sha256_before"] == result["sha256_after"]
    assert result["new_ai_model_generation_calls"] == 0
    assert result["drive_file_id_redacted"] is True
    assert result["uploaded_mp4_count"] == 1
    assert fake.upload_calls == 1 and fake.download_calls == 2
    assert os.getenv("DRAMA_ENABLE_DRIVE_UPLOAD") is None
    assert os.getenv("DRAMA_ENABLE_DRIVE_READ") is None
    data = json.loads((tmp_path/"canary"/"canary-verification.json").read_text())
    assert data == result
    assert "fakeVideo" not in json.dumps(data)
