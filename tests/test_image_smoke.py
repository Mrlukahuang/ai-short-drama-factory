"""Fully offline smoke workflow tests; never call the real Google SDK."""
from pathlib import Path

import pytest

from drama_factory.providers.google_image import (
    GeneratedImage, ImageCallDisabled, PNG_SIGNATURE,
)
from drama_factory.providers.image_smoke import run_smoke


def test_default_smoke_never_creates_image_even_if_paid_env_is_on(tmp_path, monkeypatch):
    monkeypatch.setenv("DRAMA_ENABLE_PAID_GENERATION", "YES")
    monkeypatch.setenv("GEMINI_API_KEY", "fake-test-value")
    result = run_smoke(out_dir=tmp_path)
    assert result == {
        "mode": "dry-run",
        "is_mock": True,
        "paid_model_calls": 0,
        "image_created": False,
    }
    assert list(tmp_path.iterdir()) == []


def test_paid_mode_blocked_when_environment_not_enabled(tmp_path, monkeypatch):
    monkeypatch.delenv("DRAMA_ENABLE_PAID_GENERATION", raising=False)
    monkeypatch.delenv("GEMINI_API_KEY", raising=False)
    with pytest.raises(ImageCallDisabled):
        run_smoke(paid=True, out_dir=tmp_path)
    assert list(tmp_path.iterdir()) == []


class InjectedProvider:
    def __init__(self, result):
        self.result = result
        self.calls = 0

    def generate(self, db, spec):
        self.calls += 1
        assert spec.operator_approved is True
        assert spec.actor_asset_id and spec.series_id
        return self.result


def test_injected_provider_writes_a_single_artifact(tmp_path):
    # Signature-only payload to test the file-wiring path; not a valid displayable PNG.
    data = PNG_SIGNATURE + b"smoke-test-stub-only"
    stub = InjectedProvider(
        GeneratedImage(
            model_id="gemini-nano-banana-2.1",
            sha256="a" * 64,
            png_bytes=data,
            is_mock=False,
            paid_model_calls=1,
        )
    )
    result = run_smoke(paid=True, out_dir=tmp_path, provider=stub)
    assert stub.calls == 1
    assert result["paid_model_calls"] == 1
    assert result["image_sha256"] == "a" * 64
    assert (tmp_path / "smoke_fictional_actor.png").read_bytes() == data


def test_fake_response_cannot_claim_paid_success(tmp_path):
    stub = InjectedProvider(
        GeneratedImage("gemini-nano-banana-2.1", None, None, True, 0)
    )
    with pytest.raises(ValueError, match="must not return a fake"):
        run_smoke(paid=True, out_dir=tmp_path, provider=stub)
    assert list(tmp_path.iterdir()) == []
