"""G1/R1.1 Seedance official Ark wire shape: all calls use an injected local SDK stub.

No ARK_API_KEY or network needed; no actual Seedance video has been created.
"""
from __future__ import annotations

import base64
from pathlib import Path
import shutil
from types import SimpleNamespace

import pytest

from drama_factory.providers.video_provider import VideoRequest, VideoProvider, VideoResult
from drama_factory.providers.seedance_video import (
    MODEL_ID, FakeSeedanceVideoProvider, SeedanceVideoProvider,
    SeedanceVideoDisabled, SeedanceVideoResponseError,
    _download_verified_host,
)
from test_google_omni_video import make_local_video


def _request(**overrides):
    args = {
        "prompt": "两颗虚构积木沿光亮的木桌滚动，9:16",
        "reference_images": [],
        "audio_reference": None,
        "duration_seconds": 3,
        "aspect_ratio": "9:16",
        "maximum_acknowledged_spend_usd": "2.00",
        "operator_approved": False,
    }
    args.update(overrides)
    return VideoRequest(**args)


class ArkTaskStub:
    def __init__(self, statuses=("queued", "running", "succeeded")):
        self.submissions = []
        self.polls = []
        self.statuses = list(statuses)
        self.tasks = self
        self.content_generation = self

    def create(self, **kwargs):
        self.submissions.append(kwargs)
        return SimpleNamespace(id="cgt-offline123")

    def get(self, *, task_id):
        assert task_id == "cgt-offline123"
        self.polls.append(task_id)
        return SimpleNamespace(
            status=self.statuses.pop(0),
            content=SimpleNamespace(
                video_url="https://arkdocs.tos-cn-beijing.volces.com/test/offline.mp4"
            ),
        )


def test_protocol_and_fake_are_zero_call_even_without_secrets(tmp_path, monkeypatch):
    monkeypatch.delenv("ARK_API_KEY", raising=False)
    monkeypatch.delenv("DRAMA_ENABLE_PAID_GENERATION", raising=False)
    fake = FakeSeedanceVideoProvider()
    assert isinstance(fake, VideoProvider)
    assert isinstance(SeedanceVideoProvider(), VideoProvider)
    path = tmp_path / "never.mp4"
    result = fake.generate_video(_request(), path)
    assert isinstance(result, VideoResult)
    assert result.model_id == MODEL_ID
    assert result.mp4_path is None and result.task_id is None
    assert result.actual_fee_usd is None
    assert result.is_mock and result.model_calls == 0
    assert not path.exists()


def test_ark_disabled_and_human_gate_block_before_submission(tmp_path, monkeypatch):
    stub = ArkTaskStub()
    real = SeedanceVideoProvider(client=stub, poll_interval=0)
    destination = tmp_path / "expensive.mp4"
    monkeypatch.delenv("DRAMA_ENABLE_PAID_GENERATION", raising=False)
    with pytest.raises(SeedanceVideoDisabled, match="disabled"):
        real.generate_video(_request(operator_approved=True), destination)
    monkeypatch.setenv("DRAMA_ENABLE_PAID_GENERATION", "YES")
    with pytest.raises(SeedanceVideoDisabled, match="approval"):
        real.generate_video(_request(), destination)
    with pytest.raises(SeedanceVideoDisabled, match="ARK_API_KEY"):
        SeedanceVideoProvider().generate_video(
            _request(operator_approved=True), destination
        )
    assert stub.submissions == [] and not destination.exists()


def test_reference_payload_uses_official_types_and_inline_local_bytes(tmp_path):
    img = tmp_path / "drawing.png"
    snd = tmp_path / "original.wav"
    img.write_bytes(b"\x89PNG\r\n" + b"A" * 150)
    snd.write_bytes(b"RIFF" + b"0" * 150)
    stub = ArkTaskStub(statuses=("failed",))
    provider = SeedanceVideoProvider(stub, poll_interval=0)
    # This mock test never performs a network request; content is inspected at
    # the stub then the task explicitly fails after one submission.
    with pytest.raises(SeedanceVideoResponseError, match="ended"):
        provider.generate_video(
            _request(
                operator_approved=True,
                reference_images=[img],
                audio_reference=snd,
            ),
            tmp_path / "never.mp4",
        )
    fields = stub.submissions[0]
    assert fields["model"] == "doubao-seedance-2-5-260628"
    assert fields["duration"] == 3
    assert fields["ratio"] == "9:16"
    assert fields["output_format"] == "mp4"
    assert fields["generate_audio"] is True
    data = fields["content"]
    assert data[0] == {"type": "text", "text": _request().prompt}
    assert data[1]["type"] == "image_url"
    assert data[1]["role"] == "reference_image"
    assert base64.b64decode(
        data[1]["image_url"]["url"].split(",", 1)[1]
    ) == img.read_bytes()
    assert data[2]["type"] == "audio_url"
    assert data[2]["role"] == "reference_audio"
    assert base64.b64decode(
        data[2]["audio_url"]["url"].split(",", 1)[1]
    ) == snd.read_bytes()
    assert len(stub.submissions) == 1


@pytest.mark.parametrize("name", [
    "relative.jpg", "unknown.txt", "missing.png",
])
def test_invalid_reference_files_fail_before_billable_request(tmp_path, name, monkeypatch):
    stub = ArkTaskStub()
    monkeypatch.setenv("DRAMA_ENABLE_PAID_GENERATION", "YES")
    with pytest.raises(SeedanceVideoDisabled):
        SeedanceVideoProvider(stub).generate_video(
            _request(reference_images=[tmp_path / name], operator_approved=True),
            tmp_path / "out.mp4",
        )
    assert not stub.submissions


def test_invalid_audio_and_existing_output_block_submission(tmp_path, monkeypatch):
    stub = ArkTaskStub()
    monkeypatch.setenv("DRAMA_ENABLE_PAID_GENERATION", "YES")
    bad_audio = tmp_path / "voice.mp4"
    bad_audio.write_bytes(b"not valid")
    provider = SeedanceVideoProvider(stub)
    with pytest.raises(SeedanceVideoDisabled):
        provider.generate_video(
            _request(audio_reference=bad_audio, operator_approved=True),
            tmp_path / "out.mp4",
        )
    existing = tmp_path / "exists.mp4"
    existing.write_bytes(b"already exists")
    with pytest.raises(SeedanceVideoDisabled, match="overwrite"):
        provider.generate_video(
            _request(operator_approved=True), existing
        )
    assert not stub.submissions


@pytest.mark.skipif(not shutil.which("ffmpeg"), reason="local FFmpeg needed")
def test_one_ark_task_local_sdk_result_mp4_and_honest_unknown_charge(
    tmp_path, monkeypatch,
):
    monkeypatch.setenv("DRAMA_ENABLE_PAID_GENERATION", "YES")
    input_video = make_local_video(tmp_path / "synthetic.mp4")
    calls = []
    def local_download(url, path):
        calls.append(url)
        path.write_bytes(input_video.read_bytes())
    sdk = ArkTaskStub()
    out = tmp_path / "clip.mp4"
    result = SeedanceVideoProvider(
        sdk, downloader=local_download, poll_interval=0, max_polls=3,
    ).generate_video(_request(operator_approved=True), out)
    assert result.mp4_path == out
    assert out.read_bytes() == input_video.read_bytes()
    assert result.task_id == "cgt-offline123"
    assert result.actual_fee_usd is None  # No invoice can be verified here
    assert result.model_id == MODEL_ID
    assert not result.is_mock and result.model_calls == 1
    assert len(sdk.submissions) == 1
    assert len(sdk.polls) == 3
    assert len(calls) == 1


def test_unknown_status_does_not_auto_retry_or_resubmit(tmp_path, monkeypatch):
    monkeypatch.setenv("DRAMA_ENABLE_PAID_GENERATION", "YES")
    sdk = ArkTaskStub(statuses=("unexpected",))
    with pytest.raises(SeedanceVideoResponseError, match="Unknown"):
        SeedanceVideoProvider(
            sdk, poll_interval=0, max_polls=1,
        ).generate_video(_request(operator_approved=True), tmp_path / "unused.mp4")
    assert len(sdk.submissions) == 1
    assert len(sdk.polls) == 1


def test_timeout_does_not_resubmit(tmp_path, monkeypatch):
    monkeypatch.setenv("DRAMA_ENABLE_PAID_GENERATION", "YES")
    sdk = ArkTaskStub(statuses=("queued", "running"))
    with pytest.raises(SeedanceVideoResponseError, match="do not resubmit"):
        SeedanceVideoProvider(
            sdk, poll_interval=0, max_polls=2,
        ).generate_video(_request(operator_approved=True), tmp_path / "unused.mp4")
    assert len(sdk.submissions) == 1


@pytest.mark.parametrize("host", [
    "https://evil.example/clip.mp4",
    "http://arkdocs.tos-cn-beijing.volces.com/clip.mp4",
    "https://volces.com.evil.example/clip.mp4",
    "https://user:pass@arkdocs.tos-cn-beijing.volces.com/clip.mp4",
])
def test_default_downloader_rejects_untrusted_url_before_network(host, tmp_path):
    with pytest.raises(SeedanceVideoResponseError, match="Untrusted"):
        _download_verified_host(host, tmp_path / "no-video.mp4")
    assert not (tmp_path / "no-video.mp4").exists()
