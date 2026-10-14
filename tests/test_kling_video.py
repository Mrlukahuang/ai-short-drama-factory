"""G1/R1.2 Kling official Omni contract; all tests use offline stub clients."""
from __future__ import annotations

import base64
import shutil

import pytest

from drama_factory.providers.video_provider import VideoProvider, VideoRequest, VideoResult
from drama_factory.providers.kling_video import (
    API_URL, MODEL_ID, KlingVideoProvider, FakeKlingVideoProvider,
    KlingVideoDisabled, KlingVideoResponseError, _download_kling_video,
)
from test_google_omni_video import make_local_video


def req(**updates):
    data = {
        "prompt": "Two animated paper boats in a fictional harbor",
        "reference_images": [],
        "audio_reference": None,
        "duration_seconds": 5,
        "aspect_ratio": "9:16",
        "maximum_acknowledged_spend_usd": "2.00",
        "operator_approved": False,
    }
    data.update(updates)
    return VideoRequest(**data)


class OfflineKling:
    def __init__(self, statuses=("submitted", "processing", "succeed")):
        self.calls = []
        self.statuses = list(statuses)
    def __call__(self, method, url, key, payload=None):
        self.calls.append((method, url, key, payload))
        if method == "POST":
            return {"code": 0, "data": {"task_id": "offline_kling_task"}}
        current = self.statuses.pop(0)
        return {
            "code": 0,
            "data": {
                "task_status": current,
                "task_result": {
                    "videos": [{"url": "https://p2-kling.klingai.com/cdn/video.mp4"}]
                },
                "final_balance_deduction": {"quota": "50", "list_price": "100"},
            },
        }


def test_fake_protocol_zero_calls_and_configurable_model(tmp_path, monkeypatch):
    monkeypatch.delenv("KLING_API_KEY", raising=False)
    monkeypatch.delenv("DRAMA_ENABLE_PAID_GENERATION", raising=False)
    fake = FakeKlingVideoProvider()
    live = KlingVideoProvider()
    assert isinstance(fake, VideoProvider)
    assert isinstance(live, VideoProvider)
    result = fake.generate_video(req(), tmp_path / "not_created.mp4")
    assert isinstance(result, VideoResult)
    assert result.model_id == "kling-v3-omni"
    assert result.mp4_path is None and result.task_id is None
    assert result.actual_fee_usd is None and result.model_calls == 0
    assert result.is_mock and not (tmp_path / "not_created.mp4").exists()
    assert FakeKlingVideoProvider("kling-v4-omni").generate_video(
        req(), tmp_path / "future.mp4"
    ).model_id == "kling-v4-omni"


def test_gate_disabled_approval_and_key_before_transport(tmp_path, monkeypatch):
    stub = OfflineKling()
    provider = KlingVideoProvider(transport=stub)
    dest = tmp_path / "clip.mp4"
    monkeypatch.delenv("DRAMA_ENABLE_PAID_GENERATION", raising=False)
    with pytest.raises(KlingVideoDisabled, match="disabled"):
        provider.generate_video(req(operator_approved=True), dest)
    monkeypatch.setenv("DRAMA_ENABLE_PAID_GENERATION", "YES")
    with pytest.raises(KlingVideoDisabled, match="approval"):
        provider.generate_video(req(), dest)
    monkeypatch.delenv("KLING_API_KEY", raising=False)
    with pytest.raises(KlingVideoDisabled, match="KLING_API_KEY"):
        provider.generate_video(req(operator_approved=True), dest)
    assert not stub.calls


def test_official_payload_reference_mapping_and_invalid_audio(tmp_path, monkeypatch):
    monkeypatch.setenv("DRAMA_ENABLE_PAID_GENERATION", "YES")
    monkeypatch.setenv("KLING_API_KEY", "offline_test_only")
    img = tmp_path / "ref.png"
    img.write_bytes(b"\x89PNG\r\n" + b"synthetic reference" * 3)
    transport = OfflineKling(("failed",))
    p = KlingVideoProvider(transport=transport, poll_interval=0)
    with pytest.raises(KlingVideoResponseError, match="failed"):
        p.generate_video(
            req(operator_approved=True, reference_images=[img]),
            tmp_path / "out.mp4",
        )
    method, url, key, payload = transport.calls[0]
    assert (method, url, key) == ("POST", API_URL, "offline_test_only")
    assert payload["model_name"] == MODEL_ID
    assert payload["prompt"] == req().prompt
    assert payload["mode"] == "pro" and payload["sound"] == "on"
    assert payload["aspect_ratio"] == "9:16" and payload["duration"] == "5"
    assert base64.b64decode(payload["image_list"][0]["image_url"]) == img.read_bytes()
    assert len(transport.calls) == 2
    with pytest.raises(KlingVideoDisabled, match="audio reference"):
        p.generate_video(
            req(operator_approved=True, audio_reference=tmp_path / "audio.wav"),
            tmp_path / "never.mp4",
        )
    assert len(transport.calls) == 2


@pytest.mark.parametrize("model", ["https://evil", "../../evil", "", "other-4"])
def test_invalid_model_cannot_be_submitted(model, tmp_path, monkeypatch):
    monkeypatch.setenv("DRAMA_ENABLE_PAID_GENERATION", "YES")
    monkeypatch.setenv("KLING_API_KEY", "offline_test_only")
    stub = OfflineKling()
    with pytest.raises(KlingVideoDisabled):
        KlingVideoProvider(model_id=model, transport=stub).generate_video(
            req(operator_approved=True), tmp_path / "unused.mp4",
        )
    assert not stub.calls


@pytest.mark.parametrize("duration", [3, 4, 16, 30])
def test_out_of_range_duration_fails_without_submitting(duration, tmp_path, monkeypatch):
    monkeypatch.setenv("DRAMA_ENABLE_PAID_GENERATION", "YES")
    monkeypatch.setenv("KLING_API_KEY", "offline_test_only")
    stub = OfflineKling()
    with pytest.raises(KlingVideoDisabled):
        KlingVideoProvider(transport=stub).generate_video(
            req(duration_seconds=duration, operator_approved=True),
            tmp_path / "unused.mp4",
        )
    assert not stub.calls


@pytest.mark.skipif(not shutil.which("ffmpeg"), reason="local FFmpeg required")
def test_real_local_mp4_from_injected_kling_result_and_null_usd(
    tmp_path, monkeypatch,
):
    monkeypatch.setenv("DRAMA_ENABLE_PAID_GENERATION", "YES")
    monkeypatch.setenv("KLING_API_KEY", "offline_test_only")
    video = make_local_video(tmp_path / "synthetic.mp4")
    # Current stub video is only 3s while Kling request minimum 5s:
    # create a 5s local source using FFmpeg.
    import subprocess
    subprocess.run([
        "ffmpeg", "-hide_banner", "-loglevel", "error", "-y",
        "-f", "lavfi", "-i", "testsrc2=size=480x640:rate=15",
        "-t", "5", "-c:v", "libx264", "-preset", "ultrafast",
        "-pix_fmt", "yuv420p", str(video),
    ], check=True, capture_output=True, timeout=90)
    stub = OfflineKling()
    urls = []
    def downloader(url, output):
        urls.append(url)
        output.write_bytes(video.read_bytes())
    result = KlingVideoProvider(
        transport=stub, downloader=downloader, poll_interval=0, max_polls=3
    ).generate_video(req(operator_approved=True), tmp_path / "generated.mp4")
    assert result.model_id == MODEL_ID
    assert result.mp4_path.is_file()
    assert result.task_id == "offline_kling_task"
    assert result.actual_fee_usd is None  # quota units are not USD invoices
    assert result.model_calls == 1 and result.is_mock is False
    assert len(urls) == 1
    assert [x[0] for x in stub.calls] == ["POST", "GET", "GET", "GET"]


def test_unknown_status_no_automatic_resubmission(tmp_path, monkeypatch):
    monkeypatch.setenv("DRAMA_ENABLE_PAID_GENERATION", "YES")
    monkeypatch.setenv("KLING_API_KEY", "offline_test_only")
    transport = OfflineKling(statuses=("unknown",))
    with pytest.raises(KlingVideoResponseError, match="Unknown"):
        KlingVideoProvider(transport=transport, poll_interval=0).generate_video(
            req(operator_approved=True), tmp_path / "never.mp4",
        )
    assert sum(method == "POST" for method, *_ in transport.calls) == 1


@pytest.mark.parametrize("url", [
    "https://evil.example/video.mp4",
    "http://p2-kling.klingai.com/video.mp4",
    "https://klingai.com.evil.example/video.mp4",
    "https://u:p@p2-kling.klingai.com/video.mp4",
])
def test_reject_untrusted_download_host_without_network(tmp_path, url):
    with pytest.raises(KlingVideoResponseError, match="Untrusted"):
        _download_kling_video(url, tmp_path / "fail.mp4")
    assert not (tmp_path / "fail.mp4").exists()
