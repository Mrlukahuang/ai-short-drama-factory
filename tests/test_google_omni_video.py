"""All Omni Video tests use fake SDK clients and local FFmpeg; never call Google."""
import base64
import json
import shutil
import subprocess
from pathlib import Path
from types import SimpleNamespace

import pytest

from drama_factory.providers.google_omni_video import (
    FakeOmniVideoProvider, GoogleOmniVideoProvider, InvalidVideoResponse,
    OmniVideoSpec, VideoCallDisabled, parse_google_video_file_id,
    google_video_download_uri,
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
        assert file == (
            "https://generativelanguage.googleapis.com/v1beta/"
            "files/generated123:download?alt=media"
        )
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
            # Exact Google official REST example shape, not a simplified stub.
            uri="https://generativelanguage.googleapis.com/v1beta/files/generated123:download?alt=media",
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


def test_real_documented_uri_suffix_parsed_correctly():
    """Regression for Actions run 38229227030: ':download?alt=media' is NOT part of the file ID."""
    uri = "https://generativelanguage.googleapis.com/v1beta/files/generated123:download?alt=media"
    assert parse_google_video_file_id(uri) == "generated123"
    assert parse_google_video_file_id("files/generated123") == "generated123"
    assert parse_google_video_file_id(
        "https://generativelanguage.googleapis.com/v1beta/files/id_123-abc"
    ) == "id_123-abc"
    assert google_video_download_uri("id_123-abc") == (
        "https://generativelanguage.googleapis.com/v1beta/files/id_123-abc:download?alt=media"
    )


@pytest.mark.parametrize("invalid_uri", [
    "https://evil.example/v1beta/files/generated123:download?alt=media",
    "http://generativelanguage.googleapis.com/v1beta/files/generated123",
    "https://generativelanguage.googleapis.com.evil.example/v1beta/files/generated123",
    "https://generativelanguage.googleapis.com/v1beta/files/../secret:download",
    "https://generativelanguage.googleapis.com/v1beta/files/generated123:download#fragment",
    "https://generativelanguage.googleapis.com/v1beta/other/generated123",
    "files/../../generated123",
    "files/generated123:delete",
    "https://user:pass@generativelanguage.googleapis.com/v1beta/files/generated123",
])
def test_provider_rejects_untrusted_video_uri(invalid_uri):
    with pytest.raises(InvalidVideoResponse):
        parse_google_video_file_id(invalid_uri)


@pytest.mark.skipif(not shutil.which("ffmpeg"), reason="ffmpeg required")
def test_recovery_receipt_and_download_only_never_create_another_video(tmp_path, monkeypatch):
    monkeypatch.setenv("DRAMA_ENABLE_PAID_GENERATION", "YES")
    source = make_local_video(tmp_path / "mock-video.mp4")
    stub = ClientStub(source)
    provider = GoogleOmniVideoProvider(stub, poll_interval=0, max_polls=4)
    first = provider.generate(video_spec(approved=True), tmp_path / "first.mp4")
    assert first["model_calls"] == 1
    metadata_file = tmp_path / "first.recovery.json"
    metadata = json.loads(metadata_file.read_text())
    assert metadata["file_id"] == "generated123"
    assert metadata["generation_submitted"] is True
    assert "api_key" not in str(metadata).lower()
    assert "https:" not in str(metadata)
    # A completely new client can recover from the file ID while paid mode is DISABLED.
    monkeypatch.delenv("DRAMA_ENABLE_PAID_GENERATION", raising=False)
    new_stub = ClientStub(source)
    new_provider = GoogleOmniVideoProvider(new_stub, poll_interval=0, max_polls=4)
    recovered = new_provider.recover_existing(
        metadata["file_id"], tmp_path / "recovered.mp4", operator_approved=True,
    )
    assert recovered["model_calls"] == 0
    assert recovered["recovered_existing"] is True
    assert new_stub.calls == []  # Critical: recovery NEVER calls interactions.create!
    assert new_stub.files.download_count == 1
    assert (tmp_path / "recovered.mp4").read_bytes() == source.read_bytes()


def test_recovery_requires_manual_approval(tmp_path):
    stub = ClientStub(tmp_path / "no-file.mp4")
    provider = GoogleOmniVideoProvider(stub, poll_interval=0)
    with pytest.raises(VideoCallDisabled):
        provider.recover_existing("generated123", tmp_path / "file.mp4")
    with pytest.raises(InvalidVideoResponse):
        provider.recover_existing("../secret", tmp_path / "file.mp4", operator_approved=True)
    assert stub.calls == []
    assert stub.files.download_count == 0
