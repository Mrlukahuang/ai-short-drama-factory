"""TxLab v4 one-use authority was consumed by Actions #38505044059.

Static fail-closed regression: this test never opens a DB or uses Secrets.
It deliberately runs on both normal Python CI versions, without libsql SDK.
"""
from pathlib import Path
import re


ROOT = Path(__file__).resolve().parents[1] / ".github" / "workflows"
_TXLAB = (
    "manual-isolated-libsql-txlab.yml",
    "manual-isolated-libsql-txlab-v2.yml",
    "manual-isolated-libsql-txlab-v3.yml",
    "manual-isolated-libsql-txlab-v4.yml",
)


def test_all_consumed_txlab_write_workflows_have_explicit_hard_false_gate():
    for filename in _TXLAB:
        content = (ROOT / filename).read_text(encoding="utf-8")
        # A successful one-time history check is insufficient on its own;
        # the job must be unconditionally false for ANY dispatch/input/rerun.
        assert re.search(
            r"(?m)^\s*if:\s*\$\{\{\s*false\s*&&\s*github\.ref\s*==",
            content,
        ), f"consumed TxLab workflow must be permanently hard-locked: {filename}"


def test_consumed_v4_records_verifiable_run_and_keeps_secondary_guards():
    content = (ROOT / "manual-isolated-libsql-txlab-v4.yml").read_text("utf-8")
    assert "38505044059" in content
    assert "CONSUMED" in content
    assert "github.run_attempt == 1" in content
    assert "RUN_ISOLATED_TXLAB_V4_ONCE" in content
    assert 'count" != "1"' in content
    assert "DRAMA_TXLAB_DATABASE_URL" in content
    assert "DRAMA_TXLAB_AUTH_TOKEN" in content
    assert "drama-isolated-libsql-txlab-single-run" in content
    # Do not change to schedule/push/PR invocation: historical v4 canary
    # is still visible solely for audit, not to enable automatic writes.
    assert "  workflow_dispatch:" in content
    assert "\n  push:" not in content
    assert "\n  schedule:" not in content
