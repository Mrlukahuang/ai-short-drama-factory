"""F2: typed felt Omni adapter for the existing P-final CLI and stage files.

Six-shot paid calls are *never* implicit. The P-final deterministic Fake
storyline stays separate from actual provider receipts, and native audio
is never silently replaced by synthetic voice or music.
"""
from __future__ import annotations

import hashlib
import importlib.util
import json
from decimal import Decimal
from pathlib import Path

from drama_factory.providers.google_omni_video import OmniVideoSpec

# Google published 360p output 1931 tokens/sec at USD17.50 per million.
# Charge calculation is an ESTIMATE, not a verified bill or vendor hard cap.
GOOGLE_360P_PER_SECOND = Decimal("0.0337925")
WORST_OMNI_DURATION = 10
MAX_RUN_USD = Decimal("2.00")


class FeltOmniPipelineError(ValueError):
    pass


def _style_script():
    path = Path(__file__).resolve().with_name("felt_style_omni_test.py")
    spec = importlib.util.spec_from_file_location("felt_style_for_pipeline", path)
    if spec is None or spec.loader is None:
        raise FeltOmniPipelineError("Local felt style prompt builder missing")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _sha(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            h.update(block)
    return h.hexdigest()


def _write_json(path: Path, payload: dict) -> None:
    if path.is_symlink():
        raise FeltOmniPipelineError("Linked stage file denied")
    temp = path.with_name("." + path.name + ".part")
    if temp.is_symlink():
        raise FeltOmniPipelineError("Linked temporary file denied")
    temp.write_text(json.dumps(payload, ensure_ascii=False, sort_keys=True,
                               indent=2) + "\n", encoding="utf-8")
    temp.replace(path)


def run_felt_omni_episode(source: Path, output_root: Path, *,
                          provider, style: str = "felt_diorama",
                          paid: bool = False,
                          acknowledge_fake_approvals: bool = False,
                          rerun_from: str | None = None,
                          budget_limit_usd: Decimal = MAX_RUN_USD) -> dict:
    """Process 6 provider clips, using the P-final 11-stage JSON interfaces.

    Fake-only injected providers are allowed in offline CI. No paid call may
    start unless the pessimistic six-call estimate fits the strict budget.
    An interrupted/unknown task is NEVER resubmitted automatically.
    """
    import fake_episode as original
    if style != "felt_diorama":
        raise FeltOmniPipelineError("Only owner-adopted felt_diorama style supported")
    if acknowledge_fake_approvals is not True:
        raise FeltOmniPipelineError("Explicit approval of synthetic storyboard required")
    if rerun_from not in (None, *original.STEPS):
        raise FeltOmniPipelineError("Unknown stage")
    if paid and budget_limit_usd > MAX_RUN_USD:
        raise FeltOmniPipelineError("Cannot expand AMEND-004 single run limit")
    style_mod = _style_script()
    preset = style_mod.load_preset()
    plan = style_mod.full_episode_prompts(preset)
    worst = GOOGLE_360P_PER_SECOND * WORST_OMNI_DURATION * len(plan)
    if paid and worst > budget_limit_usd:
        raise FeltOmniPipelineError(
            "Six Omni calls cannot be bounded below USD 2 with a 10s output ceiling"
        )
    if provider is None:
        raise FeltOmniPipelineError("Explicit Provider instance required")
    src = Path(source)
    if src.is_symlink() or not src.is_file():
        raise FeltOmniPipelineError("Local original synopsis required")
    out = Path(output_root)
    if out.is_symlink():
        raise FeltOmniPipelineError("Linked output root denied")

    # The existing Fake pipeline is the source of 00–04 (Bible, screenplay,
    # structured character/scene IDs). It does not authorize actual actors.
    base = original.run_fake_episode(
        src, out / "storyboard-source", target_seconds=60,
        acknowledge_fake_approvals=True,
    )
    fake_folder = Path(base["run_dir"])
    source_sha = json.loads(
        (fake_folder / "00_input.json").read_text("utf-8")
    )["source_sha256"]
    folder = out / ("omni-" + source_sha[:20] + "-felt_diorama")
    if folder.is_symlink():
        raise FeltOmniPipelineError("Linked Omni run directory denied")
    folder.mkdir(parents=True, exist_ok=True)
    for name in original.STEPS[:5]:
        raw = json.loads((fake_folder / (name + ".json")).read_text("utf-8"))
        # Preserve exact existing envelope; clarify the provenance.
        raw["source_mode"] = "synthetic_storyboard_data"
        _write_json(folder / (name + ".json"), raw)

    # Paid calls use a per-shot immutable record. Unknown/pending receipt
    # MUST be handled by an operator, not a blind repeated API submission.
    normalized = []
    receipts = []
    from drama_factory.providers.google_omni_video import InvalidVideoResponse
    for i, shot in enumerate(plan):
        key = shot["id"]
        target = folder / (key + ".mp4")
        record_path = folder / (key + ".task.json")
        signature = hashlib.sha256(
            (source_sha + preset["id"] + shot["prompt"]).encode("utf-8")
        ).hexdigest()
        receipt = None
        if record_path.exists():
            if record_path.is_symlink():
                raise FeltOmniPipelineError("Linked provider task receipt denied")
            record = json.loads(record_path.read_text("utf-8"))
            if (record.get("signature") != signature
                    or record.get("status") != "complete"
                    or record.get("is_mock") is not (not paid)
                    or not target.is_file() or target.is_symlink()
                    or record.get("video_sha256") != _sha(target)):
                raise FeltOmniPipelineError(
                    "Provider request/receipt unknown: never auto-resubmit"
                )
            receipt = record
        if receipt is None:
            # Explicit --rerun-from never overrides a previously charged shot.
            _write_json(record_path, {
                "signature": signature, "status": "started",
                "model": "gemini-omni-1.1-flash", "is_mock": not paid,
            })
            spec = OmniVideoSpec(
                prompt=shot["prompt"], resolution="360p",
                aspect_ratio="9:16", min_duration_seconds=3,
                maximum_acknowledged_spend_usd=MAX_RUN_USD,
                operator_approved=paid,
            )
            response = provider.generate(spec, target)
            if (response.get("is_mock") is not (not paid)
                    or (paid and response.get("model_calls") != 1)
                    or (not paid and response.get("model_calls") != 0)
                    or response.get("model") not in (None, "gemini-omni-1.1-flash")):
                raise FeltOmniPipelineError("Untrusted Provider call receipt")
            info = style_mod.probe(target)
            if not style_mod.is_portrait(info):
                raise InvalidVideoResponse("Landscape output: no automatic paid retry")
            if not info["has_audio"]:
                raise InvalidVideoResponse("Omni native audio missing")
            receipt = {
                "signature": signature, "status": "complete",
                "shot_id": key, "model": "gemini-omni-1.1-flash",
                "is_mock": not paid,
                "video_sha256": _sha(target),
                "provider_task_id": response.get("provider_task_id"),
                "estimated_usd": str(
                    GOOGLE_360P_PER_SECOND * Decimal(str(info["duration"]))
                ) if paid else "0",
                "actual_fee_usd": None,
                "native_audio_present": True,
                "width": info["width"], "height": info["height"],
                "duration_seconds": info["duration"],
                "prompt_sha256": hashlib.sha256(shot["prompt"].encode()).hexdigest(),
                "model_calls": response["model_calls"],
            }
            _write_json(record_path, receipt)
        norm = folder / (key + ".normalized.mp4")
        if norm.is_symlink():
            raise FeltOmniPipelineError("Linked normalized clip denied")
        if not norm.exists():
            style_mod.normalize(target, norm, has_audio=True)
        normalized.append(norm)
        receipts.append(receipt)

    spent_est = sum(Decimal(r["estimated_usd"]) for r in receipts)
    real_calls = sum(r["model_calls"] for r in receipts)
    source_mode = "omni_real" if paid else "omni_stub"
    stages = {
        "05_shots": {"shots": receipts, "video_source": source_mode,
                     "provider": "gemini-omni-1.1-flash",
                     "estimated_total_usd": str(spent_est),
                     "actual_total_usd": None if paid else "0"},
        "06_dialogue": {"route": "model_native_audio", "voice_real": paid,
                        "native_audio_by_shot": [x["native_audio_present"] for x in receipts]},
        "07_subtitles": {"status": "not_transcribed_or_aligned",
                         "verification_pending": True},
        "08_music": {"route": "model_native_audio", "music_separately_generated": False},
    }
    for name, data in stages.items():
        _write_json(folder / (name + ".json"), {
            "step": name, "provider": source_mode,
            "source_sha256": source_sha, "payload": data,
            "model_calls": real_calls, "fake_only": not paid,
        })
    final = folder / ("episode.omni.mp4" if paid else "episode.omni-stub.mp4")
    if not final.exists():
        style_mod.concat(normalized, final)
    inspected = style_mod.probe(final)
    if not style_mod.is_portrait(inspected) or not inspected["has_audio"]:
        raise FeltOmniPipelineError("Final vertical/native-audio check failed")
    render = {
        "step": "09_render", "mp4": final.name, "mp4_sha256": _sha(final),
        "width": inspected["width"], "height": inspected["height"],
        "duration_seconds": inspected["duration"],
        "provider": source_mode, "fake_only": not paid,
    }
    qa = {
        "step": "10_qa", "technical_portrait_passed": True,
        "native_audio_track_present": True, "subtitle_alignment_pending": True,
        "human_film_review_required": True,
        "model_calls": real_calls, "estimated_total_usd": str(spent_est),
        "actual_total_usd": None if paid else "0",
        "publish_approved": False, "fake_only": not paid,
    }
    _write_json(folder / "09_render.json", render)
    _write_json(folder / "10_qa.json", qa)
    return {"run_dir": str(folder), "mp4_path": str(final),
            "shots": receipts, **qa}
