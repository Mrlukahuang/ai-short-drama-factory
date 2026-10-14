"""G1/R1.3 common VideoProvider contract: ALL offline, zero Google calls."""
from pathlib import Path
from types import SimpleNamespace
import shutil

import pytest
from pydantic import ValidationError

from drama_factory.providers.video_provider import (
    VideoProvider, VideoRequest, VideoResult,
)
from drama_factory.providers.google_omni_video import (
    FakeOmniVideoProvider, GoogleOmniVideoProvider, VideoCallDisabled,
)
from test_google_omni_video import ClientStub, make_local_video


def request(**changes):
    values = {
        "prompt": "One continuous fictional rolling ball, vertical frame",
        "reference_images": [],
        "audio_reference": None,
        "duration_seconds": 3,
        "aspect_ratio": "9:16",
        "maximum_acknowledged_spend_usd": "2.00",
        "operator_approved": False,
    }
    values.update(changes)
    return VideoRequest(**values)


def test_protocol_runtime_and_fake_zero_cost_no_files_or_credentials(tmp_path, monkeypatch):
    monkeypatch.delenv("GEMINI_API_KEY", raising=False)
    monkeypatch.delenv("DRAMA_ENABLE_PAID_GENERATION", raising=False)
    fake = FakeOmniVideoProvider()
    real = GoogleOmniVideoProvider()
    assert isinstance(fake, VideoProvider)
    assert isinstance(real, VideoProvider)
    dest = tmp_path / "nonexistent.mp4"
    result = fake.generate_video(request(), dest)
    assert isinstance(result, VideoResult)
    assert result.model_id == "gemini-omni-1.1-flash"
    assert result.mp4_path is None
    assert result.task_id is None
    assert result.actual_fee_usd is None
    assert result.is_mock is True and result.model_calls == 0
    assert not dest.exists()


@pytest.mark.parametrize("fields", [
    {"reference_images": [Path("/private/local-portrait.png")]},
    {"audio_reference": Path("/private/local-voice.wav")},
    {"aspect_ratio": "16:9"},
    {"duration_seconds": 11},
])
def test_unsupported_fields_rejected_by_fake_and_real_before_any_sdk_call(
    fields, tmp_path, monkeypatch,
):
    monkeypatch.setenv("DRAMA_ENABLE_PAID_GENERATION", "YES")
    stub = ClientStub(tmp_path / "not-created.mp4")
    dest = tmp_path / "would-charge.mp4"
    spec = request(**fields, operator_approved=True)
    with pytest.raises(VideoCallDisabled):
        FakeOmniVideoProvider().generate_video(spec, dest)
    with pytest.raises(VideoCallDisabled):
        GoogleOmniVideoProvider(stub, poll_interval=0).generate_video(spec, dest)
    assert stub.calls == []
    assert not dest.exists()


def test_common_request_validates_bounds_and_required_budget():
    with pytest.raises(ValidationError):
        request(duration_seconds=2)
    with pytest.raises(ValidationError):
        request(duration_seconds=31)
    with pytest.raises(ValidationError):
        request(maximum_acknowledged_spend_usd="0")
    with pytest.raises(ValidationError):
        request(prompt="")
    with pytest.raises(ValidationError):
        request(aspect_ratio="4:3")


def test_common_interface_respects_paid_and_operator_gates_without_sdk_calls(
    tmp_path, monkeypatch,
):
    stub = ClientStub(tmp_path / "never-generated.mp4")
    real = GoogleOmniVideoProvider(stub, poll_interval=0)
    dest = tmp_path / "result.mp4"
    monkeypatch.delenv("DRAMA_ENABLE_PAID_GENERATION", raising=False)
    with pytest.raises(VideoCallDisabled, match="disabled"):
        real.generate_video(request(operator_approved=True), dest)
    monkeypatch.setenv("DRAMA_ENABLE_PAID_GENERATION", "YES")
    with pytest.raises(VideoCallDisabled, match="approve"):
        real.generate_video(request(), dest)
    assert stub.calls == []
    assert not dest.exists()


@pytest.mark.skipif(not shutil.which("ffmpeg"), reason="ffmpeg local fake SDK receipt test")
def test_common_google_adapter_returns_verified_mp4_and_actual_sdk_task_id(
    tmp_path, monkeypatch,
):
    monkeypatch.setenv("DRAMA_ENABLE_PAID_GENERATION", "YES")
    input_video = make_local_video(tmp_path / "input.mp4")
    stub = ClientStub(input_video)
    original_create = stub.create

    def interaction_with_id(**kwargs):
        value = original_create(**kwargs)
        value.id = "interactions/offline_test_123"
        return value

    stub.interactions = SimpleNamespace(create=interaction_with_id)
    output = tmp_path / "clip.mp4"
    result = GoogleOmniVideoProvider(
        stub, poll_interval=0, max_polls=3,
    ).generate_video(request(operator_approved=True), output)
    assert isinstance(result, VideoResult)
    assert result.mp4_path == output
    assert result.mp4_path.read_bytes() == input_video.read_bytes()
    assert result.task_id == "interactions/offline_test_123"
    assert result.actual_fee_usd is None  # No verified provider invoice.
    assert not result.is_mock and result.model_calls == 1
    assert stub.files.download_count == 1
    assert len(stub.calls) == 1
    assert stub.calls[0]["input"] == request().prompt
    assert stub.calls[0]["response_format"]["delivery"] == "uri"


@pytest.mark.skipif(not shutil.which("ffmpeg"), reason="ffmpeg local fake SDK receipt test")
def test_missing_task_id_is_null_not_fabricated(tmp_path, monkeypatch):
    monkeypatch.setenv("DRAMA_ENABLE_PAID_GENERATION", "YES")
    input_video = make_local_video(tmp_path / "input.mp4")
    stub = ClientStub(input_video)  # SDK fake intentionally has no interaction.id
    result = GoogleOmniVideoProvider(
        stub, poll_interval=0, max_polls=3,
    ).generate_video(
        request(operator_approved=True), tmp_path / "clip.mp4",
    )
    assert result.task_id is None
    assert result.actual_fee_usd is None
    assert result.mp4_path.is_file()


def test_common_result_does_not_invent_verified_charges_or_task_id():
    result = VideoResult(
        model_id="provider-test", mp4_path=None, task_id=None,
        actual_fee_usd=None, model_calls=0, is_mock=True,
    )
    assert result.model_dump()["actual_fee_usd"] is None
    with pytest.raises(ValidationError):
        VideoResult(
            model_id="provider-test", actual_fee_usd="-0.01",
            model_calls=0, is_mock=True,
        )
