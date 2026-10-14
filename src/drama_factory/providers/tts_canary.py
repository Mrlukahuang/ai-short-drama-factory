"""One-shot, strictly synthetic Gemini TTS canary. NOT an episode TTS worker.

Scope: ONE original fictional phrase, ONE prebuilt provider voice, no books,
no Series assets, no DB, no retry. Response written to private CI Artifact.
An attempt (including an ACK-lost exception) consumes this experimental
authorization; never auto-resubmit and never infer actual vendor billing.
"""
from __future__ import annotations

import json
import os
from pathlib import Path

from drama_factory.providers.gemini_tts_contract import (
    GeminiTtsContractDenied, inspect_gemini_tts_unary_response,
)

MODEL = "gemini-3.8-flash-lite-tts"
TEXT = "Hello from a fictional short film."
VOICE = "Kore"
_CONFIRMATION = "RUN_FICTIONAL_TTS_ONLY_ONCE"


class TtsCanaryDenied(ValueError):
    """No external exception, source text or API token may enter this error."""


def _allowed_once() -> None:
    if (
        os.getenv("DRAMA_TTS_CANARY_CONFIRM") != _CONFIRMATION
        or os.getenv("DRAMA_TTS_CANARY_MAX_USD") != "2.00"
        or os.getenv("GITHUB_REF") != "refs/heads/main"
        or os.getenv("GITHUB_RUN_ATTEMPT") != "1"
        or os.getenv("DRAMA_ENABLE_PAID_GENERATION") != "YES"
    ):
        raise TtsCanaryDenied("One-use fictional TTS budget and provenance gate denied")


def execute_one_original_tts_canary(client, destination: Path) -> dict:
    """Issue exactly one Interactions API request; never poll or retry.

    Only call after the GitHub single-merge, attempt-one/history gate. The
    provided client must be injected from one deliberately gated caller.
    """
    _allowed_once()
    dest = Path(destination)
    if dest.is_symlink() or dest.exists():
        raise TtsCanaryDenied("Refusing to overwrite any existing TTS output")
    if dest.suffix.lower() != ".wav":
        raise TtsCanaryDenied("Original fictional TTS output must be WAV")
    if client is None or not hasattr(getattr(client, "interactions", None), "create"):
        raise TtsCanaryDenied("TTS SDK client unavailable")
    payload = {
        "model": MODEL,
        "input": [{
            "type": "user_input",
            "content": [{
                "type": "text", "text": TEXT,
                "annotations": [{"type": "speech_metadata", "style": "calm and clear"}],
            }],
        }],
        "response_format": {"type": "audio"},
        "generation_config": {"speech_config": [{"voice": VOICE}]},
    }
    # Absolutely no replay path exists. In case of a network timeout or an
    # invalid/unknown receipt, the provider might already have billed once.
    try:
        interaction = client.interactions.create(**payload)
    except Exception:
        raise TtsCanaryDenied("Single TTS request outcome ambiguous; do not retry") from None
    try:
        block = interaction.output_audio
        base64_data = block.data
        inspected = inspect_gemini_tts_unary_response(base64_data, 12)
    except (AttributeError, GeminiTtsContractDenied, TypeError):
        raise TtsCanaryDenied("Single TTS attempt produced unusable WAV; do not retry") from None
    dest.parent.mkdir(parents=True, exist_ok=True)
    try:
        with dest.open("xb") as file:
            file.write(inspected.wav_bytes)
    except OSError:
        raise TtsCanaryDenied("TTS audio could not be stored; do not retry") from None
    receipt = {
        "mode": "isolated_one_original_tts_phrase",
        "model": MODEL,
        "prebuilt_voice": VOICE,
        "remote_tts_attempted": True,
        "remote_wav_format_verified": True,
        "wav_sha256": inspected.sha256,
        "wav_duration_seconds": round(inspected.duration_seconds, 3),
        "paid_request_attempts": 1,
        "vendor_billing_verified": False,
        "vendor_hard_spend_cap_verified": False,
        "original_user_content_submitted": False,
        "production_database_touched": False,
        "real_actor_voice_or_licensing_verified": False,
        "approved_for_publication": False,
        "consumed_experiment_may_retry": False,
    }
    return receipt


def main() -> int:
    try:
        _allowed_once()
        key = os.getenv("GEMINI_API_KEY")
        if not key:
            raise TtsCanaryDenied("Dedicated API key missing; no TTS request attempted")
        from google import genai
        client = genai.Client(api_key=key)
        output = Path("artifacts/original-one-use-tts.wav")
        safe = execute_one_original_tts_canary(client, output)
        print(json.dumps(safe, sort_keys=True))
        return 0
    except TtsCanaryDenied as exc:
        print(str(exc))
        return 1
    except Exception:
        print("Fictional TTS canary failed safely; do not retry")
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
