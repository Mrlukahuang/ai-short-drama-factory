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


def test_prompts_include_style_but_only_onscreen_characters():
    preset = fs.load_preset()
    for shot in fs.SHOTS:
        prompt = fs.build_prompt(preset, shot)
        assert "needle-felted" in prompt and "9:16" in prompt
        for key, description in preset["characters"].items():
            assert (description in prompt) == (key in shot["cast"])
    street = fs.build_prompt(preset, fs.SHOTS[0])
    assert preset["characters"]["female_lead"] not in street
    assert "unlisted characters" in street


def test_six_shot_felt_plan_consistency_and_split_action():
    preset = fs.load_preset()
    plan = fs.full_episode_prompts(preset)
    assert len(plan) == 6
    assert len({x["id"] for x in plan}) == 6
    assert sum(s["seconds"] for s in plan) == 52
    assert len([x for x in plan if x.get("complex_action")]) == 2
    assert all(x["seconds"] <= 6 for x in plan if x.get("complex_action"))
    for row in plan:
        assert row["prompt"] == fs.build_prompt(preset, row)
        for key, description in preset["characters"].items():
            assert (description in row["prompt"]) == (key in row["cast"])
    with pytest.raises(ValueError, match="<=6s"):
        fs.build_prompt(preset, {**plan[2], "seconds": 8})
    with pytest.raises(ValueError, match="unique"):
        fs.build_prompt(preset, {**plan[0], "cast": ["male_lead", "male_lead"]})


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
