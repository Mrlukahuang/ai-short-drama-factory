"""F2: full injected Omni stub through existing 11-stage Fake-first CLI.

NO real Omni API calls; video bytes are synthetic ffmpeg color test bars.
"""
from __future__ import annotations

import importlib.util
import json
from pathlib import Path
import shutil
import subprocess

import pytest


def _load(filename):
    path = Path(__file__).resolve().parents[1] / "scripts" / filename
    spec = importlib.util.spec_from_file_location("f2_" + path.stem, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


bridge = _load("felt_omni_episode.py")


class SyntheticOmni:
    def __init__(self):
        self.calls = []

    def generate(self, spec, destination):
        self.calls.append(spec)
        assert spec.resolution == "360p"
        assert spec.aspect_ratio == "9:16"
        assert "needle-felted" in spec.prompt
        assert spec.operator_approved is False
        subprocess.run([
            "ffmpeg", "-hide_banner", "-loglevel", "error", "-nostdin",
            "-y", "-f", "lavfi", "-i",
            "color=c=forestgreen:s=360x640:r=15:d=3",
            "-f", "lavfi", "-i", "sine=frequency=450:duration=3",
            "-shortest", "-c:v", "libx264", "-pix_fmt", "yuv420p",
            "-c:a", "aac", str(destination),
        ], check=True, capture_output=True, timeout=90)
        return {"model": "gemini-omni-1.1-flash", "is_mock": True,
                "model_calls": 0, "provider_task_id": None}


def _fixture():
    return Path(__file__).resolve().parent / "fixtures" / "felt_episode_synopsis.txt"


def test_f2_refuses_non_authorized_style_and_live_over_budget(tmp_path):
    fake = SyntheticOmni()
    with pytest.raises(bridge.FeltOmniPipelineError, match="style"):
        bridge.run_felt_omni_episode(
            _fixture(), tmp_path / "out", provider=fake,
            style="other", acknowledge_fake_approvals=True,
        )
    with pytest.raises(bridge.FeltOmniPipelineError, match="USD 2"):
        bridge.run_felt_omni_episode(
            _fixture(), tmp_path / "out", provider=fake, paid=True,
            acknowledge_fake_approvals=True,
        )
    assert fake.calls == []
    assert not (tmp_path / "out").exists()


@pytest.mark.skipif(
    not shutil.which("ffmpeg") or not shutil.which("ffprobe"),
    reason="local synthetic video codecs required",
)
def test_f2_six_stub_clips_native_audio_and_eleven_stages(tmp_path):
    stub = SyntheticOmni()
    output = tmp_path / "out"
    result = bridge.run_felt_omni_episode(
        _fixture(), output, provider=stub,
        acknowledge_fake_approvals=True,
    )
    assert len(stub.calls) == 6
    assert result["fake_only"] is True
    assert result["model_calls"] == 0
    assert result["actual_total_usd"] == "0"
    assert result["native_audio_track_present"] is True
    assert result["subtitle_alignment_pending"] is True
    assert result["publish_approved"] is False
    assert Path(result["mp4_path"]).is_file()
    for n in [f"{i:02d}" for i in range(11)]:
        assert len(list(Path(result["run_dir"]).glob(n + "_*.json"))) == 1
    render = json.loads(
        (Path(result["run_dir"]) / "09_render.json").read_text("utf-8")
    )
    assert render["width"] == 360 if "width" in render else render["payload"]["width"] == 360
    second = bridge.run_felt_omni_episode(
        _fixture(), output, provider=stub,
        acknowledge_fake_approvals=True,
    )
    assert len(stub.calls) == 6
    assert second["mp4_path"] == result["mp4_path"]
    assert second["model_calls"] == 0


@pytest.mark.skipif(not shutil.which("ffmpeg"), reason="FFmpeg required")
def test_f2_completed_source_is_not_auto_resubmitted_after_corruption(tmp_path):
    stub = SyntheticOmni()
    result = bridge.run_felt_omni_episode(
        _fixture(), tmp_path / "out", provider=stub,
        acknowledge_fake_approvals=True,
    )
    folder = Path(result["run_dir"])
    first = folder / "f01_street.mp4"
    first.write_bytes(b"tampered")
    with pytest.raises(bridge.FeltOmniPipelineError, match="never auto-resubmit"):
        bridge.run_felt_omni_episode(
            _fixture(), tmp_path / "out", provider=stub,
            acknowledge_fake_approvals=True, rerun_from="05_shots",
        )
    assert len(stub.calls) == 6
