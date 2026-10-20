"""G4 FND-02/03: build an actual Omni image+text payload, but NEVER submit it.

This is the dry-run/Fake edge between FND-01/03 and the historical
prompt-only provider. Neither approval grants nor byte-verification are
provider calls. A separate Owner-controlled real adapter and cost/rights
review are necessary before externally transmitting the payload.
Google Interactions reference conventions (2026-10): IMAGE_REF_N starts at
zero and FIRST_FRAME / LAST_FRAME denote distinct leading image roles.
"""
from __future__ import annotations

import base64
import re
from dataclasses import dataclass
from pathlib import Path

from drama_factory.pipeline.visual_keyframe_graph import (
    FrameGraphError, shot_frame_entry,
)
from drama_factory.pipeline.visual_media_admission import (
    MediaAdmissionError, _plan_shot, admit_shot_media, digest_json, verify_png,
)

OMNI_MODEL = "gemini-omni-1.1-flash"
SCHEMA = "g4-omni-reference-envelope.v1"
_TAGS = re.compile(r"<(?:IMAGE_REF_\d+|FIRST_FRAME|LAST_FRAME)>")


@dataclass(frozen=True)
class OmniMediaCapability:
    """Deliberately LOCAL limits, not a claim of provider-guaranteed quotas."""

    model_id: str = OMNI_MODEL
    max_reference_images: int = 8
    max_combined_inline_bytes: int = 3_000_000
    max_individual_png_bytes: int = 3_000_000
    supports_first_frame: bool = True
    supports_last_frame: bool = True

    def check(self) -> None:
        if (self.model_id != OMNI_MODEL
                or type(self.max_reference_images) is not int
                or not 1 <= self.max_reference_images <= 10
                or type(self.max_combined_inline_bytes) is not int
                or not 100 <= self.max_combined_inline_bytes <= 3_500_000
                or type(self.max_individual_png_bytes) is not int
                or not 100 <= self.max_individual_png_bytes <= 4_000_000
                or type(self.supports_first_frame) is not bool
                or type(self.supports_last_frame) is not bool):
            raise MediaAdmissionError("Unsupported offline provider capability")


@dataclass(frozen=True)
class OfflineOmniEnvelope:
    """Short-lived ephemeral object; never serialize request_payload in logs."""

    request_payload: dict  # includes base64 image bytes; ephemeral local only
    receipt: dict          # contains only hash/role data, not paths or image bytes


def _frame_image(frame: dict | None, path: Path | None, *,
                 cap: OmniMediaCapability, role: str) -> tuple[dict, bytes] | None:
    if frame is None:
        if path is not None:
            raise MediaAdmissionError("Frame path without approved storyboard slot")
        return None
    if type(frame) is not dict or not isinstance(path, Path):
        raise MediaAdmissionError("Storyboard frame bytes unavailable")
    if (role == "first_frame" and not cap.supports_first_frame
            or role == "last_frame" and not cap.supports_last_frame):
        raise MediaAdmissionError("Provider frame mode unsupported")
    data = verify_png(path, frame.get("png_sha256"),
                      max_bytes=cap.max_individual_png_bytes)
    meta = {
        "role": role, "png_sha256": frame["png_sha256"],
        "source_shot_id": frame["shot_id"],
        "scene_id": frame["scene_id"],
    }
    return meta, data


def prepare_offline_omni_envelope(
    plan: dict, shot_id: str, *, original_prompt: str,
    reference_paths: list[Path], operator_grant: dict,
    verification_key: bytes,
    frame_graph: dict | None = None,
    first_frame_path: Path | None = None,
    last_frame_path: Path | None = None,
    capability: OmniMediaCapability | None = None,
    now_epoch: int | None = None,
) -> OfflineOmniEnvelope:
    """Build exact media-order input and Fake receipt; external usage disabled.

    HMAC must be minted in an independent explicit operator action covering
    ordered images (all reference PNGs, then first PNG, then last PNG).
    A real use still requires a separate submission permission, cost cap,
    privacy review and integration with a production Provider.
    """
    cap = capability or OmniMediaCapability()
    cap.check()
    shot = _plan_shot(plan, shot_id)
    if (type(original_prompt) is not str or not original_prompt.strip()
            or len(original_prompt) > 7500 or _TAGS.search(original_prompt)):
        raise MediaAdmissionError("Invalid or ambiguous source screenplay prompt")
    if frame_graph is None:
        if first_frame_path is not None or last_frame_path is not None:
            raise FrameGraphError("Reference frames require a trusted frame graph")
        first, last = None, None
        frame_graph_sha = None
    else:
        if frame_graph.get("visual_plan_sha256") != plan["plan_sha256"]:
            raise FrameGraphError("Storyboard frame graph does not match asset plan")
        frame = shot_frame_entry(frame_graph, shot_id)
        first, last = frame["first_frame"], frame["last_frame"]
        frame_graph_sha = frame_graph["graph_sha256"]
    first_pair = _frame_image(first, first_frame_path, cap=cap, role="first_frame")
    last_pair = _frame_image(last, last_frame_path, cap=cap, role="last_frame")
    if last_pair is not None and first_pair is None:
        raise MediaAdmissionError("LAST_FRAME requires FIRST_FRAME")
    extras = [frame["png_sha256"] for frame in (first, last) if frame is not None]
    refs, raw_refs = admit_shot_media(
        plan, shot_id, reference_paths,
        grant=operator_grant, verification_key=verification_key,
        now_epoch=now_epoch, max_bytes=cap.max_individual_png_bytes,
        additional_verified_sha256=extras,
    )
    frame_pairs = [p for p in (first_pair, last_pair) if p is not None]
    total = len(refs) + len(frame_pairs)
    if total > cap.max_reference_images:
        raise MediaAdmissionError("Reference plus frame count exceeds provider policy")
    media_bytes = [buf for _, buf in frame_pairs] + raw_refs
    # Bound inline payload size after base64 expansion (without persisting bytes).
    if sum(4 * ((len(buf) + 2) // 3) for buf in media_bytes) > cap.max_combined_inline_bytes:
        raise MediaAdmissionError("Encoded reference payload too large for local policy")
    tags = []
    if first_pair:
        tags.append("<FIRST_FRAME>")
    if last_pair:
        tags.append("<LAST_FRAME>")
    for i, ref in enumerate(refs):
        tags.append(f"<IMAGE_REF_{i}>")
    # Tags are in the same logical sequence as the input array, but reference
    # numbering begins at zero, independent of first/last slots.
    guide = [
        "Use the referenced assets to retain fixed character identity, wardrobe, "
        "scene layout and props between shots. Do not collage or split the frame.",
    ]
    for i, item in enumerate(refs):
        guide.append(
            f"<IMAGE_REF_{i}> is the fixed {item['role']} "
            f"{item['asset_id']} (asset version {item['asset_version']}); "
            "use as visual reference, not a literal first frame."
        )
    if first_pair:
        guide.append("<FIRST_FRAME> is the approved start image of this shot.")
    if last_pair:
        guide.append("<LAST_FRAME> is the approved end image of this shot.")
    prompt = "\n".join(guide) + "\n" + original_prompt
    if len(prompt) > 9000:
        raise MediaAdmissionError("Reference-augmented Omni prompt exceeds limit")
    input_parts = [
        {"type": "image", "data": base64.b64encode(buf).decode("ascii"),
         "mime_type": "image/png"}
        for buf in media_bytes
    ] + [{"type": "text", "text": prompt}]
    request = {
        "model": cap.model_id,
        "input": input_parts,
        "response_format": {
            "type": "video", "aspect_ratio": "9:16",
            "resolution": "360p", "delivery": "uri",
        },
    }
    all_meta = [meta for meta, _ in frame_pairs] + refs
    receipt = {
        "schema": SCHEMA, "shot_id": shot_id,
        "visual_plan_sha256": plan["plan_sha256"],
        "episode_draft_sha256": plan.get("episode_draft_sha256"),
        "frame_graph_sha256": frame_graph_sha,
        "model_id": cap.model_id,
        "original_prompt_sha256": __import__("hashlib").sha256(
            original_prompt.encode("utf-8")).hexdigest(),
        "media": all_meta, "model_input_roles": tags,
        "request_fingerprint_sha256": digest_json({
            "model": cap.model_id, "media": all_meta, "prompt": prompt,
            "response_format": request["response_format"],
        }),
        "dry_run_serialization_verified": True,
        "legal_rights_independently_verified_by_code": False,
        "provider_reference_applied": False,
        "model_submission_allowed": False,
        "model_calls": 0, "actual_fee_usd": None,
    }
    return OfflineOmniEnvelope(request_payload=request, receipt=receipt)


class FakeOmniReferenceProvider:
    """Receives an exact prepared payload without an external provider call."""

    def evaluate(self, envelope: OfflineOmniEnvelope) -> dict:
        if not isinstance(envelope, OfflineOmniEnvelope):
            raise MediaAdmissionError("A validated offline envelope is required")
        if (envelope.receipt.get("model_submission_allowed") is not False
                or envelope.receipt.get("provider_reference_applied") is not False
                or envelope.request_payload.get("model") != OMNI_MODEL
                or type(envelope.request_payload.get("input")) is not list
                or not envelope.request_payload["input"]
                or envelope.request_payload["input"][-1].get("type") != "text"):
            raise MediaAdmissionError("Unsafe or incomplete offline model envelope")
        return {
            "is_mock": True, "model_calls": 0, "actual_fee_usd": None,
            "provider_reference_applied": False,
            "request_fingerprint_sha256":
                envelope.receipt["request_fingerprint_sha256"],
        }
