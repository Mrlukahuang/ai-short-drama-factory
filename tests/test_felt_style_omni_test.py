import importlib.util
import shutil
import subprocess
from decimal import Decimal
from pathlib import Path

import pytest

_spec = importlib.util.spec_from_file_location(
    "felt_style_omni_test",
    Path(__file__).resolve().parents[1] / "scripts" / "felt_style_omni_test.py",
)
fs = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(fs)


def test_prompts_include_style_and_both_characters():
    preset = fs.load_preset()
    for shot in fs.SHOTS:
        p = fs.build_prompt(preset, shot)
        assert "needle-felted" in p and "9:16" in p
        assert "A-Jie" in p and "Xiao-Yu" in p
        assert preset["consistency_rule"] in p


def test_budget_within_limits():
    plan = fs.plan_budget(len(fs.SHOTS))
    assert Decimal(plan["per_shot_estimate_usd"]) <= fs.PER_SHOT_LIMIT_USD
    assert Decimal(plan["total_estimate_usd"]) <= fs.TOTAL_LIMIT_USD


def test_budget_refuses_too_many_shots():
    with pytest.raises(RuntimeError):
        fs.plan_budget(20)


def test_portrait_check():
    assert fs.is_portrait({"width": 360, "height": 640})
    assert not fs.is_portrait({"width": 1280, "height": 720})


class _FakeOmni:
    """Writes a synthetic clip; first call landscape to exercise the single retry."""

    def __init__(self):
        self.calls = 0

    def generate(self, spec, destination):
        self.calls += 1
        size = "640x360" if self.calls == 1 else "360x640"
        subprocess.run(["ffmpeg", "-v", "error", "-y", "-f", "lavfi", "-i",
                        f"testsrc=size={size}:rate=30:duration=1",
                        "-f", "lavfi", "-i", "sine=frequency=440:duration=1",
                        "-shortest", "-c:v", "libx264", "-pix_fmt", "yuv420p",
                        "-c:a", "aac", str(destination)], check=True)
        return {"is_mock": True, "model_calls": 1, "provider_task_id": None}


@pytest.mark.skipif(not shutil.which("ffmpeg"), reason="ffmpeg not installed")
def test_run_retries_landscape_once_and_concats(tmp_path):
    fake = _FakeOmni()
    m = fs.run(tmp_path, fake)
    assert fake.calls == 4  # shot1 landscape + retry, shot2, shot3
    assert m["final_mp4"] == "felt_style_3shot.mp4"
    assert (tmp_path / "felt_style_3shot.mp4").stat().st_size > 0
    assert m["all_portrait"] is True
    assert Decimal(m["estimated_spend_usd"]) <= fs.TOTAL_LIMIT_USD
