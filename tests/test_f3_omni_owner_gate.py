"""AMEND-006 F3: owner-budget condition MUST short-circuit before paid API."""
from pathlib import Path
import importlib.util
from decimal import Decimal
import json

import pytest


def _script():
    path = Path(__file__).resolve().parents[1] / "scripts/f3_omni_report.py"
    spec = importlib.util.spec_from_file_location("f3_report_test", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_f3_budget_preflight_never_authorizes_over_usd2():
    f3 = _script()
    x = f3.preflight()
    assert x["model"] == "gemini-omni-1.1-flash"
    assert x["shots"] == 6 and x["resolution"] == "360p"
    assert x["worst_case_video_output_usd"] == "2.0275500"
    assert Decimal(x["worst_case_video_output_usd"]) > Decimal("2")
    assert x["all_checks_satisfied"] is False
    assert x["real_requests_made"] == 0
    assert x["blocking_issue"] == 137
    assert x["actual_provider_fee_usd"] is None


def test_f3_preflight_writes_an_auditable_block_receipt(tmp_path):
    f3 = _script()
    dest = tmp_path / "preflight.json"
    with pytest.raises(f3.F3BudgetBlocked, match="Issue #137"):
        f3.main(["--preflight", "--out", str(dest)])
    x = json.loads(dest.read_text("utf-8"))
    assert x["all_checks_satisfied"] is False
    assert x["real_requests_made"] == 0


def test_f3_no_phantom_real_artifact_from_stub(tmp_path):
    f3 = _script()
    with pytest.raises((ValueError, FileNotFoundError, KeyError)):
        f3.build_delivery_manifest(tmp_path)


def test_f3_manual_workflow_runs_preflight_before_secret_or_generate():
    path = Path(__file__).resolve().parents[1] / ".github/workflows/f3-felt-omni-sixshot.yml"
    y = path.read_text("utf-8")
    assert "workflow_dispatch" in y
    assert "secrets.GEMINI_API_KEY" in y
    assert "RUN_F3_FELT_OMNI_6" in y
    assert "--provider omni --style felt_diorama --paid" in y
    assert "--preflight" in y
    assert y.index("--preflight") < y.index("secrets.GEMINI_API_KEY")
    assert "ffprobe-binaries-only==0.1.2 --hash=sha256:" in y
    assert "--require-hashes --no-deps --only-binary=:all:" in y
    assert "command -v ffmpeg" in y and "command -v ffprobe" in y
    assert y.index("Install hash-pinned FFmpeg") < y.index("--preflight")
    assert "actions/upload-artifact@v4" in y
    assert "if-no-files-found: error" in y
