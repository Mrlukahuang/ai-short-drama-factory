from decimal import Decimal
import pytest
from pydantic import ValidationError

from drama_factory.pipeline.contracts import (
    ShotGenerationSpec, AssetVersionRef, ShotJobState, GenerationReceipt
)


def test_stable_idempotency_key_even_when_reference_order_changes():
    refs = [
      AssetVersionRef(asset_id="hero", version="v1", sha256="a" * 64),
      AssetVersionRef(asset_id="set", version="v2", sha256="b" * 64),
    ]
    base = dict(project_id="p", episode_id="e", shot_id="s", provider="google",
                model_id="gemini-omni-1.1-flash", prompt_version="p1", prompt="进入客厅",
                duration_seconds=6, budget_usd=Decimal("2.00"))
    assert ShotGenerationSpec(**base, asset_refs=refs).idempotency_key() == ShotGenerationSpec(**base, asset_refs=refs[::-1]).idempotency_key()


def test_changed_actor_version_invalidates_generation_fingerprint():
    base = dict(project_id="p", episode_id="e", shot_id="s", provider="google",
                model_id="gemini-omni-1.1-flash", prompt_version="p1", prompt="说话",
                duration_seconds=6, budget_usd=Decimal("1.00"))
    a = ShotGenerationSpec(**base, asset_refs=[AssetVersionRef(asset_id="actor", version="v1", sha256="a"*64)])
    b = ShotGenerationSpec(**base, asset_refs=[AssetVersionRef(asset_id="actor", version="v2", sha256="b"*64)])
    assert a.idempotency_key() != b.idempotency_key()


def test_invalid_reference_duplicate_and_negative_budget_rejected():
    ref = AssetVersionRef(asset_id="actor", version="v1", sha256="a"*64)
    base = dict(project_id="p", episode_id="e", shot_id="s", provider="google",
                model_id="omni", prompt_version="v1", prompt="scene", duration_seconds=6,
                budget_usd=Decimal("1.00"))
    with pytest.raises(ValidationError):
        ShotGenerationSpec(**base, asset_refs=[ref, ref])
    with pytest.raises(ValidationError):
        ShotGenerationSpec(**{**base, "budget_usd": "-0.1"})


def test_provider_receipt_does_not_claim_video_exists_on_submit():
    receipt = GenerationReceipt(idempotency_key="a" * 64, provider="google", model_id="omni",
                                provider_task_id="task123", state=ShotJobState.SUBMITTED)
    assert receipt.media_uri is None
    assert receipt.actual_cost_usd is None


def test_budget_change_does_not_invalidate_content_cache():
    base = dict(project_id="p", episode_id="e", shot_id="s", provider="google",
                model_id="omni", prompt_version="v1", prompt="scene", duration_seconds=6)
    low = ShotGenerationSpec(**base, budget_usd=Decimal("1"))
    high = ShotGenerationSpec(**base, budget_usd=Decimal("5"))
    assert low.idempotency_key() == high.idempotency_key()


def test_seed_change_does_invalidate_content_cache():
    base = dict(project_id="p", episode_id="e", shot_id="s", provider="google",
                model_id="omni", prompt_version="v1", prompt="scene", duration_seconds=6,
                budget_usd=Decimal("1"))
    assert ShotGenerationSpec(**base, seed=1).idempotency_key() != ShotGenerationSpec(**base, seed=2).idempotency_key()
