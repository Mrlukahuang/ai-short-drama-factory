"""All Omni Video tests use fake SDK clients and local FFmpeg; never call Google."""
import base64
import shutil
import subprocess
from pathlib import Path
from types import SimpleNamespace

import pytest

from drama_factory.providers.google_omni_video import (
    FakeOmniVideoProvider, GoogleOmniVideoProvider, InvalidVideoResponse,
    OmniVideoSpec, VideoCallDisabled,
)
from drama_factory.providers.omni_video_smoke import run_manual_test


def video_spec(approved=False):
    return OmniVideoSpec(
        prompt="Cinematic rolling red ball, vertical 9:16",
        operator_approved=approved,
        maximum_acknowledged_spend_usd="2.00",
    )


def make_local_video(path):
    subprocess.run([
        "ffmpeg", "-hide_banner", "-loglevel", "error", "-y",
        "-f", "lavfi", "-i", "testsrc2=size=480x640:rate=15",
        "-t", "3", "-c:v", "libx264", "-preset", "ultrafast",
        "-pix_fmt", "yuv420p", str(path),
    ], check=True, capture_output=True, text=True, timeout=90)
    return path


class FilesStub:
    def __init__(self, input_path):
        self.input_path = input_path
        self.poll_count = 0
        self.download_count = 0

    def get(self, *, name):
        assert name == "files/generated123"
        self.poll_count += 1
        state = "PROCESSING" if self.poll_count == 1 else "ACTIVE"
        return SimpleNamespace(state=SimpleNamespace(name=state))

    def download(self, *, file, destination):
        assert file.endswith("/files/generated123")
        self.download_count += 1
        Path(destination).write_bytes(self.input_path.read_bytes())


class ClientStub:
    def __init__(self, input_path):
        self.calls = []
        self.files = FilesStub(input_path)
        self.interactions = self

    def create(self, **kwargs):
        self.calls.append(kwargs)
        return SimpleNamespace(output_video=SimpleNamespace(
            uri="https://generativelanguage.googleapis.com/v1beta/files/generated123",
            data=None,
        ))


def test_video_provider_disabled_by_default(tmp_path, monkeypatch):
    monkeypatch.delenv("DRAMA_ENABLE_PAID_GENERATION", raising=False)
    stub = ClientStub(tmp_path / "missing.mp4")
    provider = GoogleOmniVideoProvider(stub, poll_interval=0)
    with pytest.raises(VideoCallDisabled):
        provider.generate(video_spec(approved=True), tmp_path / "result.mp4")
    assert stub.calls == []
    result = FakeOmniVideoProvider().generate(video_spec(), tmp_path / "x.mp4")
    assert result["model_calls"] == 0 and result["is_mock"] is True
    assert not (tmp_path / "x.mp4").exists()


def test_operator_gate_and_no_overwrite(tmp_path, monkeypatch):
    monkeypatch.setenv("DRAMA_ENABLE_PAID_GENERATION", "YES")
    stub = ClientStub(tmp_path / "missing.mp4")
    provider = GoogleOmniVideoProvider(stub, poll_interval=0)
    with pytest.raises(VideoCallDisabled):
        provider.generate(video_spec(), tmp_path / "result.mp4")
    assert stub.calls == []
    (tmp_path / "result.mp4").write_bytes(b"existing")
    with pytest.raises(InvalidVideoResponse, match="overwrite"):
        provider.generate(video_spec(approved=True), tmp_path / "result.mp4")
    assert stub.calls == []


@pytest.mark.skipif(not shutil.which("ffmpeg"), reason="ffmpeg required")
def test_one_uri_video_request_download_and_validate(tmp_path, monkeypatch):
    monkeypatch.setenv("DRAMA_ENABLE_PAID_GENERATION", "YES")
    src = make_local_video(tmp_path / "input.mp4")
    stub = ClientStub(src)
    provider = GoogleOmniVideoProvider(stub, poll_interval=0, max_polls=4)
    dest = tmp_path / "received.mp4"
    receipt = provider.generate(video_spec(approved=True), dest)
    assert receipt["is_mock"] is False and receipt["model_calls"] == 1
    assert receipt["delivery"] == "uri"
    assert receipt["source_duration_seconds"] == pytest.approx(3, abs=.2)
    assert dest.read_bytes() == src.read_bytes()
    assert stub.files.poll_count == 2 and stub.files.download_count == 1
    assert stub.calls == [{
        "model": "gemini-omni-1.1-flash",
        "input": "Cinematic rolling red ball, vertical 9:16",
        "response_format": {
            "type": "video", "aspect_ratio": "9:16",
            "resolution": "360p", "delivery": "uri",
        },
    }]


@pytest.mark.skipif(not shutil.which("ffmpeg"), reason="ffmpeg required")
def test_inline_fallback_decodes_mp4_without_network(tmp_path, monkeypatch):
    monkeypatch.setenv("DRAMA_ENABLE_PAID_GENERATION", "YES")
    source = make_local_video(tmp_path / "input.mp4")
    video = SimpleNamespace(uri=None, data=base64.b64encode(source.read_bytes()).decode("ascii"))
    stub = SimpleNamespace(interactions=SimpleNamespace(create=lambda **kw: SimpleNamespace(output_video=video)))
    receipt = GoogleOmniVideoProvider(stub).generate(video_spec(approved=True), tmp_path / "from_inline.mp4")
    assert receipt["delivery"] == "inline"
    assert receipt["model_calls"] == 1


@pytest.mark.skipif(not shutil.which("ffmpeg"), reason="ffmpeg required")
def test_model_video_enters_complete_episode_without_additional_calls(tmp_path):
    source = make_local_video(tmp_path / "stub_output.mp4")

    class Injected:
        def generate(self, spec, dest):
            assert spec.operator_approved is True
            Path(dest).write_bytes(source.read_bytes())
            return {
                "is_mock": False, "model_calls": 1, "media_path": str(dest),
                "source_sha256": "0" * 64,
            }

    outcome = run_manual_test(tmp_path / "delivery", paid=True, provider=Injected())
    assert outcome["provider_calls"] == 1
    assert outcome["preview"]["supplied_local_clips"] == 1
    assert outcome["preview"]["media"]["subtitle_codec"] == "mov_text"
    assert Path(outcome["final_mp4"]).is_file()
