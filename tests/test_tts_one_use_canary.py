"""One-shot real TTS entrypoint must be impossible to replay from CI by accident."""
from __future__ import annotations

import base64
import io
import wave
from pathlib import Path
from types import SimpleNamespace

import pytest

from drama_factory.providers.tts_canary import (
    TEXT, MODEL, VOICE, TtsCanaryDenied, execute_one_original_tts_canary,
)


def _original_wav():
    stream = io.BytesIO()
    with wave.open(stream, "wb") as wav:
        wav.setnchannels(1)
        wav.setsampwidth(2)
        wav.setframerate(24000)
        wav.writeframes(b"\x00\x00" * 24000)
    return base64.b64encode(stream.getvalue()).decode("ascii")


class FakeInteractionClient:
    def __init__(self, *, fail=False, bad_audio=False):
        self.inputs = []
        self.fail = fail
        self.bad_audio = bad_audio
        self.interactions = self

    def create(self, **kw):
        self.inputs.append(kw)
        if self.fail:
            raise RuntimeError("SECRET_API_KEY should never appear")
        return SimpleNamespace(
            output_audio=SimpleNamespace(data="wrong" if self.bad_audio else _original_wav()),
        )


@pytest.fixture
def approved_canary_env(monkeypatch):
    monkeypatch.setenv("DRAMA_TTS_CANARY_CONFIRM", "RUN_FICTIONAL_TTS_ONLY_ONCE")
    monkeypatch.setenv("DRAMA_TTS_CANARY_MAX_USD", "2.00")
    monkeypatch.setenv("GITHUB_REF", "refs/heads/main")
    monkeypatch.setenv("GITHUB_RUN_ATTEMPT", "1")
    monkeypatch.setenv("DRAMA_ENABLE_PAID_GENERATION", "YES")


def test_one_fictional_sdk_interaction_wav_only_no_retry(tmp_path, approved_canary_env):
    client = FakeInteractionClient()
    path = tmp_path / "tts-output.wav"
    result = execute_one_original_tts_canary(client, path)
    assert len(client.inputs) == 1
    assert client.inputs[0]["model"] == MODEL
    assert client.inputs[0]["input"][0]["content"][0]["text"] == TEXT
    assert client.inputs[0]["generation_config"] == {
        "speech_config": [{"voice": VOICE}],
    }
    assert client.inputs[0]["response_format"] == {"type": "audio"}
    assert result["remote_tts_attempted"] is True
    assert result["vendor_hard_spend_cap_verified"] is False
    assert result["vendor_billing_verified"] is False
    assert result["production_database_touched"] is False
    assert result["consumed_experiment_may_retry"] is False
    assert result["paid_request_attempts"] == 1
    assert TEXT not in str(result)
    assert path.is_file()
    with wave.open(str(path), "rb") as wav:
        assert wav.getnframes() == 24000
    # Existing destination blocks even though the fake client exists;
    # absolutely no second call goes to the SDK.
    with pytest.raises(TtsCanaryDenied, match="overwrite"):
        execute_one_original_tts_canary(client, path)
    assert len(client.inputs) == 1


@pytest.mark.parametrize("bad", ["DRAMA_TTS_CANARY_CONFIRM", "DRAMA_TTS_CANARY_MAX_USD",
                                   "GITHUB_REF", "GITHUB_RUN_ATTEMPT",
                                   "DRAMA_ENABLE_PAID_GENERATION"])
def test_different_budget_or_scope_cannot_submit_even_once(
    monkeypatch, tmp_path, approved_canary_env, bad,
):
    monkeypatch.setenv(bad, "not-approved")
    client = FakeInteractionClient()
    with pytest.raises(TtsCanaryDenied, match="denied"):
        execute_one_original_tts_canary(client, tmp_path / "no.wav")
    assert client.inputs == []
    assert not (tmp_path / "no.wav").exists()


@pytest.mark.parametrize("case", ["ambiguous_commit", "bad_audio"])
def test_single_attempt_failure_is_redacted_and_never_retried(
    tmp_path, approved_canary_env, case,
):
    client = FakeInteractionClient(
        fail=(case == "ambiguous_commit"), bad_audio=(case == "bad_audio"),
    )
    file = tmp_path / "no-output.wav"
    with pytest.raises(TtsCanaryDenied) as exc:
        execute_one_original_tts_canary(client, file)
    assert len(client.inputs) == 1
    assert "SECRET_API_KEY" not in str(exc.value)
    assert "wrong" not in str(exc.value)
    assert not file.exists()


def test_workflow_is_pinned_to_one_merge_and_static_phrase():
    root = Path(__file__).resolve().parents[1]
    workflow = (root / ".github/workflows/tts-one-use-canary.yml").read_text("utf-8")
    assert "PR10-ONE-REAL-TTS-20261014" in workflow
    assert "github.run_attempt == 1" in workflow
    assert "concurrency:" in workflow
    assert "cancel-in-progress: false" in workflow
    assert "timeout-minutes: 6" in workflow
    assert "GEMINI_API_KEY: ${{ secrets.GEMINI_API_KEY }}" in workflow
    assert "RUN_FICTIONAL_TTS_ONLY_ONCE" in workflow
    assert "DRAMA_TTS_CANARY_MAX_USD: '2.00'" in workflow
    assert "event=push" in workflow
    assert "  workflow_dispatch:" not in workflow
    assert "  schedule:" not in workflow
