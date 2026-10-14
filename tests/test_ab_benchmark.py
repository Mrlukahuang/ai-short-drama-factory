"""G1/R1.5 offline 3×3 benchmark plan never triggers provider SDKs."""
from __future__ import annotations

from copy import deepcopy
from decimal import Decimal
import importlib.util
import json
from pathlib import Path
import subprocess
import sys

import pytest


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "ab_benchmark.py"
SHOTS = ROOT / "benchmarks/g1/shots.json"
spec = importlib.util.spec_from_file_location("g1_ab_benchmark", SCRIPT)
module = importlib.util.module_from_spec(spec)
assert spec.loader is not None
spec.loader.exec_module(module)


def _shots():
    return json.loads(SHOTS.read_text(encoding="utf-8"))


def test_plan_exactly_three_original_chinese_shots_three_providers_one_each():
    data = _shots()
    plan = module.build_plan(
        data, confirmation="G1-PLAN-ONLY", budget_usd="30.00",
    )
    assert plan["planned_tasks"] == 9 and plan["model_generation_calls"] == 0
    assert plan["actual_paid_spend_usd"] == "0"
    assert plan["vendor_hard_billing_cap_verified"] is False
    assert plan["execution_mode"] == "plan_only_no_paid_dispatch"
    assert len({x["shot_id"] for x in plan["tasks"]}) == 3
    assert len({x["provider_model"] for x in plan["tasks"]}) == 3
    assert all(x["attempt"] == 1 and x["duration_seconds"] == 5
               for x in plan["tasks"])
    assert all(x["actual_fee_usd"] is None
               and x["media_path"] is None
               and x["provider_task_id"] is None
               and x["model_calls"] == 0
               and x["is_real_ai_result"] is False
               for x in plan["tasks"])
    assert any("普通话" in x["prompt"] for x in plan["tasks"])
    assert data == _shots()  # no mutation


@pytest.mark.parametrize("amount", ["0", "30.01", "-1", "Infinity", "NaN", "not-price"])
def test_reject_invalid_or_over_thirty_usd_plan_budget(amount):
    with pytest.raises(ValueError):
        module.build_plan(_shots(), confirmation="G1-PLAN-ONLY", budget_usd=amount)


def test_human_confirmation_phrase_required():
    with pytest.raises(ValueError, match="confirmation"):
        module.build_plan(_shots(), confirmation="GO LIVE", budget_usd="2.00")


@pytest.mark.parametrize("edit", [
    lambda x: x["shots"].pop(),
    lambda x: x["shots"].reverse(),
    lambda x: x["shots"][0].update(shot_id="OTHER"),
    lambda x: x["shots"][0].update(duration_seconds=30),
    lambda x: x["shots"][0].update(prompt=""),
    lambda x: x.update(aspect_ratio="16:9"),
    lambda x: x.update(schema="future-schema"),
])
def test_no_variable_shot_or_model_plan_can_sneak_into_g1(edit):
    rows = deepcopy(_shots())
    edit(rows)
    with pytest.raises(ValueError):
        module.build_plan(rows, confirmation="G1-PLAN-ONLY", budget_usd="30")


def test_cli_writes_only_json_plan_without_credentials_or_media(tmp_path):
    target = tmp_path / "plan.json"
    run = subprocess.run([
        sys.executable, str(SCRIPT), "--shots", str(SHOTS),
        "--confirm", "G1-PLAN-ONLY", "--budget-usd", "30",
        "--out", str(target),
    ], capture_output=True, text=True)
    assert run.returncode == 0, run.stderr
    assert "0 generated clips" in run.stdout
    doc = json.loads(target.read_text("utf-8"))
    assert doc["planned_tasks"] == 9
    assert list(tmp_path.iterdir()) == [target]


def test_cli_does_not_have_paid_run_option(tmp_path):
    run = subprocess.run([
        sys.executable, str(SCRIPT),
        "--execute", "--confirm", "G1-PLAN-ONLY",
        "--budget-usd", "30", "--out", str(tmp_path / "video.mp4"),
    ], capture_output=True, text=True)
    assert run.returncode != 0
    assert not list(tmp_path.iterdir())


def test_workflow_never_passes_secrets_or_enables_paid_generation():
    workflow = (ROOT / ".github/workflows/video-ab-benchmark.yml").read_text("utf-8")
    assert "workflow_dispatch:" in workflow
    assert "G1-PLAN-ONLY" in workflow
    assert 'DRAMA_ENABLE_PAID_GENERATION: "NO"' in workflow
    assert "scripts/ab_benchmark.py" in workflow
    assert "--budget-usd" in workflow
    assert "upload-artifact" in workflow
    assert "KLING_API_KEY" not in workflow
    assert "ARK_API_KEY" not in workflow
    assert "GEMINI_API_KEY" not in workflow
