"""V5 consumed one-time authorization MUST remain permanently hard locked."""
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def test_consumed_v5_is_hard_locked_alongside_old_txlab_versions():
    content = (ROOT / ".github/workflows/txlab-v5-dual-runner-once.yml").read_text("utf-8")
    assert "if: ${{ false && github.ref == 'refs/heads/main'" in content
    assert "CONSUMED" in content
    assert "38509779430" in content
    assert "contains(github.event.head_commit.message, 'PR31-V5-EXECUTE-ONCE-20261014')" in content
    assert "head_sha ==" in content
    assert "workflow_dispatch" not in content
    assert "PR31-V5-EXECUTE-ONCE-20261014" in content
    assert "github.run_attempt == 1" in content
    assert "DRAMA_TXLAB_V5_MAX_USD: '2.00'" in content
    assert "cancel-in-progress: false" in content
    assert "  push:" in content and "  workflow_dispatch:" not in content
    assert "  schedule:" not in content
    assert content.count("timeout-minutes: 6") == 5
    assert content.count("runs-on: ubuntu-latest") == 5
    for entrypoint in ("setup:", "actor-a:", "actor-b:", "seal:", "observer:"):
        assert f"  {entrypoint}" in content
    for old in (
        "manual-isolated-libsql-txlab.yml",
        "manual-isolated-libsql-txlab-v2.yml",
        "manual-isolated-libsql-txlab-v3.yml",
        "manual-isolated-libsql-txlab-v4.yml",
    ):
        other = (ROOT / ".github/workflows" / old).read_text("utf-8")
        assert "if: ${{ false &&" in other


def test_v5_readonly_postmortem_once_consumed_and_locked():
    content = (ROOT / ".github/workflows/txlab-v5-readonly-diagnostic-once.yml").read_text("utf-8")
    assert "CONSUMED" in content
    assert "38510686538" in content
    assert "if: ${{ false && github.ref == 'refs/heads/main'" in content
    assert "github.run_attempt == 1" in content
    assert "DRAMA_V5_DIAG_MAX_USD: '2.00'" in content
    assert "timeout-minutes: 5" in content
    assert "  workflow_dispatch:" not in content
