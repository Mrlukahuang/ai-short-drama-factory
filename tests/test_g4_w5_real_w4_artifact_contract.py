"""W5 honest real-artifact smoke-workflow offline/rights contract.

The EXTERNAL workflow, not this static unit test, actually downloads W3
media and runs the real W4 CLI. Never let a Fake fixture become proof.
"""
from pathlib import Path


def test_w5_real_artifact_workflow_exact_pins_existing_cli_and_zero_provider_secrets():
    root=Path(__file__).resolve().parents[1]
    workflow=(root/".github/workflows/g4-w5-real-w4-artifact-smoke.yml").read_text("utf-8")
    w3=(root/"docs/handoff/W3_EVIDENCE_20261019.md").read_text("utf-8")
    w4=(root/"scripts/review_gpt_episode_offline.py").read_text("utf-8")
    assert "pull_request:" in workflow
    assert "push:" in workflow
    assert "actions: read" in workflow
    assert "DRAMA_ENABLE_PAID_GENERATION: 'NO'" in workflow
    assert "39141517448" in workflow
    # Exact GitHub artifact DISPLAY NAMES are only exposed by Actions;
    # W3 frozen handoff records artifact IDs and media SHA, not the names.
    for name in (
        "gpt-real-12shot-caption-DRAFT-39141517448",
        "gpt-W3-repaired-provenance-39141517448",
    ):
        assert name in workflow
    for term in (
        "12142320238", "12141772943",
        "d4208ccb7b4353e184eb7d003125a010e20f8dedf7a3a9bc0eee85a0e4f041f7",
        "de6d623523d8537461571b66508ee997a28e10fed23cd927900c3f8370a6df2f",
        "364016304d078e11730b858956002eb7236cdf5282bc92dfa5f80a99cdada1ad",
        "3296b63bf88f154a43efba6a8ad895243331de22a8633a7474f68b178677ecf4",
        "c6fa289f4a63192ea72d83c31dba86771fae10ee09a6ee68413ad78f7a259db6",
    ):
        assert term in workflow
        assert term in w3
    assert "python scripts/review_gpt_episode_offline.py" in workflow
    assert "--original-artifact-id 12142320238" in workflow
    assert "--fake-artifact-id 12141772943" in workflow
    assert "def main(" in w4 and "load_w3_bundle(" in w4
    assert "human_review_attested_count" in workflow
    assert "known_needs_repair_count" in workflow
    assert "release_qa" in workflow
    assert "sha256sum -c -" in workflow
    assert "ffmpeg -hide_banner" in workflow
    assert "artifacts/w5-reports/original-content-qa.json" in workflow
    assert "artifacts/w5-reports/w1_fake-content-qa.json" in workflow
    assert "artifacts/w5/original/gpt-episode-caption-draft.mp4" not in workflow.split("path: |")[-1]
    assert "artifacts/w5/w1_fake/gpt-episode-caption-draft.mp4" not in workflow.split("path: |")[-1]
    assert "upload-artifact@v4" in workflow
    assert "GEMINI_API_KEY" not in workflow
    assert "OPENAI_API_KEY" not in workflow
    assert "secrets." not in workflow
    assert "--reviews-json" not in workflow
    assert "--reviewer-key-file" not in workflow
    assert "workflow_dispatch:" in workflow
