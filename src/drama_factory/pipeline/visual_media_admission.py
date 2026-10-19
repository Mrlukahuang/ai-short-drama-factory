"""G4 FND-02: trusted local media admission for offline reference requests.

Never uploads bytes, calls a model, or changes existing W1-W5 approvals.
Rights must be separately checked by a real operator before signing a grant.
A signature authenticates the operator's declaration, not legal ownership.
"""
from __future__ import annotations

import hashlib
import hmac
import json
import re
import struct
import time
from pathlib import Path

PLAN_SCHEMA = "g4-fnd01-visual-production-plan.v1"
GRANT_SCHEMA = "g4-visual-media-operator-grant.v1"
_SHA = re.compile(r"[0-9a-f]{64}\Z")
_PNG = b"\x89PNG\r\n\x1a\n"


class MediaAdmissionError(ValueError):
    """Do not include private paths, media contents or secret values in errors."""


def digest_json(value: object) -> str:
    return hashlib.sha256(json.dumps(
        value, ensure_ascii=False, sort_keys=True, separators=(",", ":"),
        allow_nan=False,
    ).encode("utf-8")).hexdigest()


def valid_sha(value: object) -> bool:
    return type(value) is str and _SHA.fullmatch(value) is not None


def _plan_shot(plan: dict, shot_id: str) -> dict:
    if (type(plan) is not dict or plan.get("schema") != PLAN_SCHEMA
            or not valid_sha(plan.get("plan_sha256"))
            or plan["plan_sha256"] != digest_json({
                k: v for k, v in plan.items() if k != "plan_sha256"
            })
            or plan.get("model_submission_allowed") is not False
            or plan.get("provider_reference_applied") is not False
            or type(plan.get("shots")) is not list):
        raise MediaAdmissionError("Visual plan signature or schema invalid")
    match = [s for s in plan["shots"] if s.get("shot_id") == shot_id]
    if len(match) != 1:
        raise MediaAdmissionError("Unknown or duplicate shot identity")
    return match[0]


def verify_png(path: Path, expected_sha256: str, *, max_bytes: int = 4_000_000,
               max_pixels: int = 12_000_000) -> bytes:
    """Verify actual local byte content, PNG header and declared resource bounds.

    This validates a single PNG framing signature/IHDR but is not a full PNG
    decoder. The original local media importer is responsible for decoding
    and sanitizing PNGs; provider must never accept untrusted unsanitized paths.
    """
    if not valid_sha(expected_sha256) or type(path) is not Path:
        raise MediaAdmissionError("Image digest or file handle invalid")
    if (type(max_bytes) is not int or not 100 <= max_bytes <= 8_000_000
            or type(max_pixels) is not int or not 1 <= max_pixels <= 12_000_000):
        raise MediaAdmissionError("Invalid provider media limits")
    try:
        if path.is_symlink() or not path.is_file():
            raise MediaAdmissionError("Reference file cannot be trusted")
        with path.open("rb") as handle:
            data = handle.read(max_bytes + 1)
        if not 100 <= len(data) <= max_bytes:
            raise MediaAdmissionError("Reference exceeds media bytes limit")
        if hashlib.sha256(data).hexdigest() != expected_sha256:
            raise MediaAdmissionError("Reference image bytes differ from pinned SHA")
        if (data[:8] != _PNG or data[12:16] != b"IHDR"
                or data[8:12] != b"\x00\x00\x00\x0d"
                or len(data) < 33):
            raise MediaAdmissionError("Reference is not a sanitized PNG")
        width, height = struct.unpack(">II", data[16:24])
        if (width < 1 or height < 1 or width > 4096 or height > 4096
                or width * height > max_pixels):
            raise MediaAdmissionError("Reference image dimensions exceed limits")
        return data
    except (OSError, OverflowError, ValueError) as exc:
        if isinstance(exc, MediaAdmissionError):
            raise
        raise MediaAdmissionError("Reference file verification failed") from None


def _claims(plan: dict, shot_id: str, image_shas: list[str], *,
            reviewer: str, expiry_epoch: int) -> dict:
    _plan_shot(plan, shot_id)
    if (not image_shas or len(image_shas) > 10
            or any(not valid_sha(s) for s in image_shas)
            or type(reviewer) is not str or not 2 <= len(reviewer) <= 120
            or type(expiry_epoch) is not int or expiry_epoch < 1):
        raise MediaAdmissionError("Invalid media grant claims")
    return {
        "schema": GRANT_SCHEMA, "series_id": plan["series_id"],
        "shot_id": shot_id, "visual_plan_sha256": plan["plan_sha256"],
        "media_sha256_ordered": list(image_shas),
        "purpose": "external_reference_to_video",
        "reviewer": reviewer, "expires_at_epoch": expiry_epoch,
    }


def issue_operator_grant(plan: dict, shot_id: str, image_shas: list[str], *,
                         reviewer: str, expiry_epoch: int, signing_key: bytes) -> dict:
    """Explicit operator-only step. Do not call automatically in a worker.

    The caller bears responsibility for actual rights, consent, privacy and
    remote-provider policy. This method does NOT independently prove them.
    """
    if type(signing_key) is not bytes or len(signing_key) < 32:
        raise MediaAdmissionError("Missing independent operator signing key")
    claims = _claims(plan, shot_id, image_shas, reviewer=reviewer,
                     expiry_epoch=expiry_epoch)
    sig = hmac.new(signing_key, digest_json(claims).encode(), hashlib.sha256)
    return {**claims, "signature": sig.hexdigest()}


def verify_operator_grant(plan: dict, shot_id: str, image_shas: list[str], *,
                          grant: dict, verification_key: bytes,
                          now_epoch: int | None = None) -> None:
    """Fail closed on unsigned/expired/out-of-scope or reordered references."""
    if (type(grant) is not dict or type(verification_key) is not bytes
            or len(verification_key) < 32):
        raise MediaAdmissionError("Independent operator model-use grant missing")
    claims = _claims(plan, shot_id, image_shas,
                     reviewer=grant.get("reviewer"),
                     expiry_epoch=grant.get("expires_at_epoch"))
    if (set(grant) != set(claims) | {"signature"}
            or any(grant.get(k) != v for k, v in claims.items())
            or not valid_sha(grant.get("signature"))):
        raise MediaAdmissionError("Model-use grant scope mismatch")
    expected = hmac.new(verification_key, digest_json(claims).encode(),
                        hashlib.sha256).hexdigest()
    if not hmac.compare_digest(expected, grant["signature"]):
        raise MediaAdmissionError("Model-use grant signature invalid")
    now = int(time.time()) if now_epoch is None else now_epoch
    if type(now) is not int or now > claims["expires_at_epoch"]:
        raise MediaAdmissionError("Model-use grant expired")


def admit_shot_media(plan: dict, shot_id: str, image_paths: list[Path], *,
                     grant: dict, verification_key: bytes,
                     now_epoch: int | None = None,
                     max_bytes: int = 4_000_000) -> tuple[list[dict], list[bytes]]:
    """Media descriptors + bytes for a single shot; zero network activity.

    Must receive the exact positional reference list. Paths do not enter the
    returned descriptors and bytes must never be written to JSON receipts.
    """
    shot = _plan_shot(plan, shot_id)
    refs = shot.get("selected_references")
    if (type(refs) is not list or type(image_paths) is not list
            or not refs or len(image_paths) != len(refs)):
        raise MediaAdmissionError("Selected reference count or media paths mismatch")
    descriptors = []
    buffers = []
    for ref, path in zip(refs, image_paths):
        if (type(ref) is not dict or type(ref.get("image")) is not dict
                or ref.get("role") not in {"actor", "scene", "prop"}
                or not valid_sha(ref["image"].get("png_sha256"))):
            raise MediaAdmissionError("Invalid shot media descriptor")
        image = ref["image"]
        if (image.get("series_id") != plan["series_id"]
                or image.get("kind") != ref["role"]):
            raise MediaAdmissionError("Visual reference identity mismatch")
        buffers.append(verify_png(path, image["png_sha256"], max_bytes=max_bytes))
        descriptors.append({
            "role": ref["role"], "asset_id": image["asset_id"],
            "asset_version": image["asset_version"],
            "view": image["view"], "png_sha256": image["png_sha256"],
            "media_mime": "image/png",
        })
    verify_operator_grant(
        plan, shot_id, [d["png_sha256"] for d in descriptors],
        grant=grant, verification_key=verification_key, now_epoch=now_epoch,
    )
    return descriptors, buffers
