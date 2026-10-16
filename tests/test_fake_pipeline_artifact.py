"""P-final artifact checks that require no provider, user media or secret."""
from pathlib import Path
import ast
import importlib.util

import pytest


def _load(name, rel):
    file = Path(__file__).resolve().parents[1] / rel
    ast.parse(file.read_text("utf-8"), filename=str(file))
    spec = importlib.util.spec_from_file_location(name, file)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_missing_and_tampered_fake_artifact_rejected(tmp_path):
    verify = _load("fake_verify", "scripts/verify_fake_pipeline_artifact.py")
    with pytest.raises(ValueError, match="missing|Missing"):
        verify.verify_artifact(tmp_path)
    (tmp_path / "stages").mkdir()
    (tmp_path / "episode.fake.mp4").write_bytes(b"mock mp4")
    (tmp_path / "episode.sha256").write_text("0" * 64 + "  episode.fake.mp4\n")
    with pytest.raises(ValueError, match="MP4"):
        verify.verify_artifact(tmp_path)


def test_p_final_workflow_is_offline_and_uploads_real_stage_artifacts():
    yaml = (Path(__file__).resolve().parents[1]
            / ".github/workflows/p-final-fake-episode.yml").read_text("utf-8")
    for required in (
        "actions/upload-artifact@v4",
        "p-final-fake-full-episode-mp4",
        "episode.fake.mp4",
        "episode.sha256",
        "stages/*.json",
        "--acknowledge-fake-approvals",
        "DRAMA_FACTORY_OFFLINE: '1'",
        "DRAMA_ENABLE_PAID_GENERATION: 'NO'",
        "scripts/verify_fake_pipeline_artifact.py",
    ):
        assert required in yaml
    script = (Path(__file__).resolve().parents[1]
              / "scripts/fake_episode.py").read_text("utf-8")
    assert "FAKE ONLY - OFFLINE TECHNICAL PREVIEW" in script
    assert "drawtext=" in script
