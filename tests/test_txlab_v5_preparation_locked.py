"""V5 preparation MUST be hard-disabled until a reviewed activation merge."""
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def test_v5_workflow_prep_cannot_touch_turso():
    content = (ROOT / ".github/workflows/txlab-v5-dual-runner-once.yml").read_text("utf-8")
    assert "if: ${{ false && github.ref == 'refs/heads/main'" in content
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
