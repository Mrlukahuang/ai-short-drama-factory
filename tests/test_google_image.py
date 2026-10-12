"""Image adapter tests with injected SDK stub; all network activity is forbidden."""
from base64 import b64encode
from decimal import Decimal
from types import SimpleNamespace

import pytest

from drama_factory.providers.google_image import (
    FakeGoogleImageProvider, GoogleImageProvider, GoogleImageSpec,
    ImageCallDisabled, InvalidImageResponse,
)


def fixture_actor(client, label="A"):
    series_id = client.post("/api/v1/projects", json={
        "title": f"剧{label}", "premise": "测试角色",
    }).json()["series_id"]
    actor_id = client.post(f"/api/v1/series/{series_id}/assets", json={
        "kind": "actor", "key": "lead", "specification": {
            "name": "女主", "appearance": "长发", "identity_anchors": ["左眼下痣"],
        },
    }).json()["asset_id"]
    return series_id, actor_id


def spec(series, actor, **overrides):
    obj = {
        "series_id": series, "actor_asset_id": actor,
        "prompt": "Studio photorealistic portrait of a fictional actress.",
        "maximum_acknowledged_spend_usd": "1.00",
    }
    obj.update(overrides)
    return GoogleImageSpec.model_validate(obj)


class DummyInteractionClient:
    def __init__(self, data):
        self.calls = []
        self.interactions = self
        self.data = data

    def create(self, **kwargs):
        self.calls.append(kwargs)
        return SimpleNamespace(output_image=SimpleNamespace(data=self.data))


def test_mock_zero_charges_without_network(client):
    series, actor = fixture_actor(client)
    result = FakeGoogleImageProvider().generate(client.app.state.db, spec(series, actor))
    assert result.is_mock is True
    assert result.png_bytes is None and result.paid_model_calls == 0


def test_real_provider_refuses_to_call_by_default(client, monkeypatch):
    series, actor = fixture_actor(client)
    stub = DummyInteractionClient("invalid")
    monkeypatch.delenv("DRAMA_ENABLE_PAID_GENERATION", raising=False)
    with pytest.raises(ImageCallDisabled):
        GoogleImageProvider(stub).generate(client.app.state.db, spec(series, actor, operator_approved=True))
    assert stub.calls == []


def test_operator_approval_gate(client, monkeypatch):
    series, actor = fixture_actor(client)
    monkeypatch.setenv("DRAMA_ENABLE_PAID_GENERATION", "YES")
    stub = DummyInteractionClient("invalid")
    with pytest.raises(ImageCallDisabled):
        GoogleImageProvider(stub).generate(client.app.state.db, spec(series, actor))
    assert stub.calls == []


def test_injected_sdk_contract_and_png_receipt(client, monkeypatch):
    series, actor = fixture_actor(client)
    monkeypatch.setenv("DRAMA_ENABLE_PAID_GENERATION", "YES")
    png = (
        b"\x89PNG\r\n\x1a\n" + b"test-only-synthetic-png-body"
    )  # Test only: signature payload, NOT a claimed playable or visually valid image.
    stub = DummyInteractionClient(b64encode(png).decode("ascii"))
    result = GoogleImageProvider(stub).generate(
        client.app.state.db, spec(series, actor, operator_approved=True),
    )
    assert result.paid_model_calls == 1 and result.is_mock is False
    assert result.png_bytes == png
    assert len(result.sha256) == 64
    assert stub.calls == [{
        "model": "gemini-nano-banana-2.1",
        "input": "Studio photorealistic portrait of a fictional actress.",
        "response_format": {
            "type": "image", "mime_type": "image/png",
            "aspect_ratio": "9:16", "image_size": "1K",
        },
    }]


def test_bad_image_does_not_report_success(client, monkeypatch):
    series, actor = fixture_actor(client)
    monkeypatch.setenv("DRAMA_ENABLE_PAID_GENERATION", "YES")
    for bad in ("not-base64", b64encode(b"not-png").decode("ascii")):
        with pytest.raises(InvalidImageResponse):
            GoogleImageProvider(DummyInteractionClient(bad)).generate(
                client.app.state.db, spec(series, actor, operator_approved=True),
            )


def test_cross_series_and_missing_reference_binary_blocked(client):
    a, actor_a = fixture_actor(client, "A")
    b, _ = fixture_actor(client, "B")
    with pytest.raises(ValueError):
        FakeGoogleImageProvider().generate(client.app.state.db, spec(b, actor_a))
    with pytest.raises(ValueError):
        FakeGoogleImageProvider().generate(
            client.app.state.db, spec(a, actor_a, reference_id="ref_unavailable"),
        )
