"""G4/R4.4: actual Omni PNG+text Interactions contract, with FAKE SDK only.

This intentionally tests the new real adapter, NOT a production provider call,
asset ownership, account billing, or CityDiscount model generation.
"""
from __future__ import annotations

import copy
from decimal import Decimal

import pytest

from drama_factory.pipeline.omni_media_envelope import OfflineOmniEnvelope
from drama_factory.providers.google_omni_video import (
    GoogleOmniVideoProvider, VideoCallDisabled,
)
from test_g4_visual_spine_full import _fixture, _payload
from test_google_omni_video import ClientStub


def _consent(envelope, **overrides):
    result = {
        "shot_id": envelope.receipt["shot_id"],
        "request_fingerprint_sha256": envelope.receipt["request_fingerprint_sha256"],
        "source_rights_verified_by_operator": True,  # synthetic-only test declaration
        "external_model_transfer_approved": True,  # synthetic-only
        "provider_retention_terms_accepted": True,  # synthetic-only
        "already_spent_today_usd": "0",
        "max_run_spend_usd": "2.00",
    }
    result.update(overrides)
    return result


def test_actual_FND_media_payload_can_enter_one_official_omni_image_interaction(
    tmp_path, monkeypatch,
):
    monkeypatch.setenv("DRAMA_ENABLE_PAID_GENERATION", "YES")
    envelope = _payload(_fixture(tmp_path))
    sdk = ClientStub(tmp_path / "unused.mp4")
    path = tmp_path / "result.mp4"
    provider = GoogleOmniVideoProvider(sdk, poll_interval=0, max_polls=4)

    # Test the actual SDK method and exact image+text payload on plain
    # Python CI, which has no FFmpeg. Existing offline-video job tests real
    # FFmpeg source validation separately.
    def fake_verified_download(client, file_id, uri, destination, min_duration):
        assert client is sdk
        assert file_id == "generated123"
        assert uri.startswith("https://generativelanguage.googleapis.com/")
        assert min_duration == 3
        destination.write_bytes(b"fake-sdk-mp4-receipt-bytes")
        return {
            "model": "gemini-omni-1.1-flash",
            "is_mock": False, "model_calls": 0,
            "media_path": str(destination),
            "source_sha256": "0" * 64,
            "source_duration_seconds": 3.0, "delivery": "uri",
        }

    provider._download_file = fake_verified_download
    receipt = provider.generate_approved_reference_envelope(
        envelope, path, live_consent=_consent(envelope),
    )
    assert len(sdk.calls) == 1
    assert sdk.calls[0] == envelope.request_payload
    assert [x["type"] for x in sdk.calls[0]["input"]] == ["image"] * 5 + ["text"]
    assert all(x["mime_type"] == "image/png" for x in sdk.calls[0]["input"][:-1])
    assert receipt["is_mock"] is False and receipt["model_calls"] == 1
    assert receipt["provider_reference_applied"] is True
    assert receipt["reference_image_count"] == 5
    assert receipt["reference_fingerprint_sha256"] == envelope.receipt[
        "request_fingerprint_sha256"
    ]
    assert receipt["actual_fee_usd"] is None
    assert path.read_bytes() == b"fake-sdk-mp4-receipt-bytes"
    assert all(k not in receipt for k in (
        "data", "base64", "image_bytes", "request_payload",
    ))
    assert all(part["data"] not in str(receipt)
               for part in envelope.request_payload["input"][:-1])


def test_paid_and_independent_consent_gates_precede_sdk_and_files(tmp_path, monkeypatch):
    envelope = _payload(_fixture(tmp_path))
    sdk = ClientStub(tmp_path / "absent.mp4")
    provider = GoogleOmniVideoProvider(sdk, poll_interval=0)
    target = tmp_path / "must_not_create.mp4"
    monkeypatch.delenv("DRAMA_ENABLE_PAID_GENERATION", raising=False)
    with pytest.raises(VideoCallDisabled, match="disabled"):
        provider.generate_approved_reference_envelope(
            envelope, target, live_consent=_consent(envelope),
        )
    monkeypatch.setenv("DRAMA_ENABLE_PAID_GENERATION", "YES")
    for k in ["source_rights_verified_by_operator",
              "external_model_transfer_approved",
              "provider_retention_terms_accepted"]:
        with pytest.raises(VideoCallDisabled, match="consent"):
            provider.generate_approved_reference_envelope(
                envelope, target, live_consent=_consent(envelope, **{k: False}),
            )
    with pytest.raises(VideoCallDisabled):
        provider.generate_approved_reference_envelope(
            envelope, target, live_consent={},
        )
    assert sdk.calls == [] and not target.exists()


@pytest.mark.parametrize("reported,cap", [
    ("4.00", "2.00"), ("0", "2.01"), ("-1", "1"),
    ("NaN", "1"), ("Infinity", "1"), ("3.5", "1.51"),
])
def test_usd_2_per_run_and_5_nz_day_are_strict_declared_guards(
    tmp_path, monkeypatch, reported, cap,
):
    monkeypatch.setenv("DRAMA_ENABLE_PAID_GENERATION", "YES")
    envelope = _payload(_fixture(tmp_path))
    sdk = ClientStub(tmp_path / "absent.mp4")
    with pytest.raises(VideoCallDisabled, match="budget|Budget"):
        GoogleOmniVideoProvider(sdk).generate_approved_reference_envelope(
            envelope, tmp_path / "bad.mp4",
            live_consent=_consent(envelope,
                                  already_spent_today_usd=reported,
                                  max_run_spend_usd=cap),
        )
    assert sdk.calls == []


@pytest.mark.parametrize("alter", ["image", "order", "prompt", "shot", "receipt"])
def test_tampered_source_bytes_media_order_prompt_or_receipt_cannot_submit(
    tmp_path, monkeypatch, alter,
):
    monkeypatch.setenv("DRAMA_ENABLE_PAID_GENERATION", "YES")
    original = _payload(_fixture(tmp_path))
    mutated = copy.deepcopy(original.request_payload)
    receipt = copy.deepcopy(original.receipt)
    if alter == "image":
        mutated["input"][0]["data"] = mutated["input"][0]["data"][:-4] + "AAAA"
    elif alter == "order":
        mutated["input"][0], mutated["input"][1] = (
            mutated["input"][1], mutated["input"][0]
        )
    elif alter == "prompt":
        mutated["input"][-1]["text"] = "Unapproved other prompt"
    elif alter == "shot":
        receipt["shot_id"] = "s09"
    elif alter == "receipt":
        receipt["media"][1]["role"] = "foreign"
    fake = OfflineOmniEnvelope(mutated, receipt)
    sdk = ClientStub(tmp_path / "absent.mp4")
    with pytest.raises(VideoCallDisabled):
        GoogleOmniVideoProvider(sdk).generate_approved_reference_envelope(
            fake, tmp_path / "never.mp4", live_consent=_consent(original),
        )
    assert sdk.calls == []


def test_legacy_raw_VideoRequest_paths_remain_denied_for_owner_images(
    tmp_path, monkeypatch,
):
    from drama_factory.providers.video_provider import VideoRequest
    monkeypatch.setenv("DRAMA_ENABLE_PAID_GENERATION", "YES")
    sdk = ClientStub(tmp_path / "absent.mp4")
    request = VideoRequest(
        prompt="A felt Auckland treasure-hunt scene",
        reference_images=(tmp_path / "unapproved_character.png",),
        duration_seconds=5,
        maximum_acknowledged_spend_usd=Decimal("2"),
        operator_approved=True,
    )
    with pytest.raises(VideoCallDisabled, match="not implemented"):
        GoogleOmniVideoProvider(sdk).generate_video(request, tmp_path / "never.mp4")
    assert sdk.calls == []
