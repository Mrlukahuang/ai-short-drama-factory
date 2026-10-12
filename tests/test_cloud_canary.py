"""Manual cloud canary: default mock, explicit no-hidden-cloud-ops guarantee."""
from __future__ import annotations

import json
import os
import shutil
from pathlib import Path

import pytest

from drama_factory.storage.cloud_canary import (
    run_private_cloud_canary, main,
)
from drama_factory.storage.cloud_objects import (
    CloudArtifactError, CloudTarget, FakeS3ArtifactClient,
)

TARGET = CloudTarget(
    provider="r2",
    bucket="private-short-drama-canary",
    r2_account_id="d" * 32,
)

ffmpeg_required = pytest.mark.skipif(
    not (shutil.which("ffmpeg") and shutil.which("ffprobe")),
    reason="Real FFmpeg needed to produce canary media",
)


def test_live_requires_separate_manual_confirmation_before_file_or_network(tmp_path, monkeypatch):
    fake = FakeS3ArtifactClient()
    monkeypatch.delenv("DRAMA_CLOUD_SMOKE_CONFIRM", raising=False)
    monkeypatch.delenv("DRAMA_ENABLE_CLOUD_UPLOAD", raising=False)
    monkeypatch.delenv("DRAMA_ENABLE_CLOUD_READ", raising=False)
    out = tmp_path / "not-created"
    with pytest.raises(CloudArtifactError, match="confirmation"):
        run_private_cloud_canary(out, TARGET, live=True, client=fake)
    assert not out.exists()
    assert fake.put_calls == fake.get_calls == 0
    monkeypatch.setenv("DRAMA_CLOUD_SMOKE_CONFIRM", "TEST_ONE_PRIVATE_CLOUD_MP4")
    with pytest.raises(CloudArtifactError, match="permission gates"):
        run_private_cloud_canary(out, TARGET, live=True, client=fake)
    assert not out.exists()


def test_fake_mode_rejects_injected_real_provider_and_does_not_toggle_flags(tmp_path, monkeypatch):
    monkeypatch.delenv("DRAMA_ENABLE_CLOUD_UPLOAD", raising=False)
    monkeypatch.delenv("DRAMA_ENABLE_CLOUD_READ", raising=False)
    with pytest.raises(CloudArtifactError, match="FakeS3"):
        run_private_cloud_canary(tmp_path / "no-file", TARGET, client=object())
    assert os.getenv("DRAMA_ENABLE_CLOUD_UPLOAD") is None
    assert os.getenv("DRAMA_ENABLE_CLOUD_READ") is None


@ffmpeg_required
def test_fake_canary_builds_real_mp4_and_roundtrips_without_env_or_model(client, tmp_path, monkeypatch):
    monkeypatch.delenv("DRAMA_CLOUD_SMOKE_CONFIRM", raising=False)
    monkeypatch.delenv("DRAMA_ENABLE_CLOUD_UPLOAD", raising=False)
    monkeypatch.delenv("DRAMA_ENABLE_CLOUD_READ", raising=False)
    fake = FakeS3ArtifactClient()
    result = run_private_cloud_canary(
        tmp_path / "canary", TARGET, live=False, client=fake,
    )
    assert result["mode"] == "fake"
    assert result["verified"] is True
    assert result["new_ai_model_generation_calls"] == 0
    assert result["actual_cloud_charge_usd"] is None
    assert result["size_bytes"] > 1000
    assert result["source_sha256"] == result["restored_sha256"]
    assert result["signed_download_url_created"] is False
    assert fake.put_calls == 1 and fake.get_calls == 2
    assert os.getenv("DRAMA_ENABLE_CLOUD_UPLOAD") is None
    assert os.getenv("DRAMA_ENABLE_CLOUD_READ") is None
    manifest = json.loads(
        (tmp_path / "canary" / "canary-verification.json").read_text()
    )
    assert manifest == result
    assert len(list((tmp_path / "canary" / "recovered-catalog").rglob("*.mp4"))) == 1


@ffmpeg_required
def test_explicit_live_mode_with_injected_mock_exercises_exact_same_path(tmp_path, monkeypatch):
    fake = FakeS3ArtifactClient()
    monkeypatch.setenv("DRAMA_CLOUD_SMOKE_CONFIRM", "TEST_ONE_PRIVATE_CLOUD_MP4")
    monkeypatch.setenv("DRAMA_ENABLE_CLOUD_UPLOAD", "YES")
    monkeypatch.setenv("DRAMA_ENABLE_CLOUD_READ", "YES")
    output = run_private_cloud_canary(
        tmp_path / "manual-test", TARGET, live=True, client=fake,
    )
    assert output["mode"] == "live"
    assert output["verified"] is True
    assert fake.put_calls == 1 and fake.get_calls == 2


def test_cli_invalid_r2_account_fails_without_network(monkeypatch, tmp_path):
    monkeypatch.setenv("DRAMA_R2_ACCOUNT_ID", "dangerous-url.example")
    with pytest.raises(CloudArtifactError, match="account ID"):
        main(["--provider", "r2", "--out", str(tmp_path / "unused")])
    assert not (tmp_path / "unused").exists()
