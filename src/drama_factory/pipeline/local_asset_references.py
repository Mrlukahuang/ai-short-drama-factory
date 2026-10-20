"""Local, append-only visual reference gallery for an existing Series asset version.

No model calls, network requests, face recognition, ownership claims or
publication. Never handles voice samples; never modifies the Series asset DB.
Only meant for a trusted localhost operator on a private test machine.
"""
from __future__ import annotations

import hashlib
import io
import json
import os
import re
import tempfile
from pathlib import Path

from PIL import Image, ImageOps, UnidentifiedImageError

from drama_factory.db import Database

MAX_SOURCE_BYTES = 8 * 1024 * 1024
MAX_STORED_BYTES = 8 * 1024 * 1024
MAX_SOURCE_SIDE = 4096
MAX_SOURCE_PIXELS = 12_000_000
MAX_PREVIEW_SIDE = 1024
_ALLOWED_FORMATS = {"PNG", "JPEG", "WEBP"}
_KINDS = {"actor", "scene", "prop"}
_SERIES = re.compile(r"proj_[a-f0-9]{14}\Z")
_ASSET = re.compile(r"asset_[a-f0-9]{14}\Z")
_SHA = re.compile(r"[a-f0-9]{64}\Z")


class LocalReferenceError(ValueError):
    """Fixed error phrases: do not disclose paths or personal image contents."""


def _sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _asset_row(db: Database, series_id: str, asset_id: str) -> dict:
    if (type(series_id) is not str or type(asset_id) is not str
            or _SERIES.fullmatch(series_id) is None
            or _ASSET.fullmatch(asset_id) is None):
        raise LocalReferenceError("Invalid local visual reference selection")
    row = db.one(
        """SELECT id,series_id,kind,version,specification_json FROM series_assets
           WHERE id=? AND series_id=?""",
        (asset_id, series_id),
    )
    if row is None or row["kind"] not in _KINDS:
        raise LocalReferenceError("Asset version not found in selected Series")
    return row


def _owned_folder(root: Path, series_id: str, asset_id: str, *,
                  create: bool = False) -> Path:
    root = Path(root).absolute()
    folder = root / series_id / asset_id
    if any(p.is_symlink() for p in (
        root.parent, root, root / series_id, folder,
    )):
        raise LocalReferenceError("Linked local reference workspace denied")
    if create:
        folder.mkdir(parents=True, exist_ok=True)
    return folder


def _canonical_png(source: bytes) -> tuple[bytes, int, int, str]:
    try:
        with Image.open(io.BytesIO(source)) as probe:
            if probe.format not in _ALLOWED_FORMATS:
                raise ValueError("Unexpected image format")
            source_format = probe.format
            width, height = probe.size
            if (not 1 <= width <= MAX_SOURCE_SIDE
                    or not 1 <= height <= MAX_SOURCE_SIDE
                    or width * height > MAX_SOURCE_PIXELS
                    or getattr(probe, "n_frames", 1) != 1):
                raise ValueError("Source image dimension/frame bound")
            probe.verify()
        with Image.open(io.BytesIO(source)) as img:
            upright = ImageOps.exif_transpose(img)
            # Fresh RGB pixels and new PNG remove EXIF/GPS, ICC, XMP,
            # animation and any original source filename metadata.
            # Alpha must be flattened against an explicit matte before RGB.
            # Plain RGBA.convert("RGB") drops alpha and turns transparent
            # source pixels into arbitrary hidden RGB (often black), causing
            # black boxes/halos around logos and felt character sheets.
            rgba = upright.convert("RGBA")
            matte = Image.new("RGBA", rgba.size, (255, 255, 255, 255))
            matte.alpha_composite(rgba)
            clean = matte.convert("RGB")
            clean.thumbnail((MAX_PREVIEW_SIDE, MAX_PREVIEW_SIDE),
                            Image.Resampling.LANCZOS)
            out = io.BytesIO()
            clean.save(out, format="PNG")
            sanitized = out.getvalue()
            if not 100 <= len(sanitized) <= MAX_STORED_BYTES:
                raise ValueError("Normalized reference outside size bounds")
            return sanitized, clean.width, clean.height, source_format
    except (UnidentifiedImageError, OSError, ValueError,
            Image.DecompressionBombError):
        raise LocalReferenceError("Invalid or oversized local reference image") from None


def _publish_immutable(folder: Path, name: str, data: bytes) -> None:
    """Never overwrite old content, even when upload is repeated or concurrent."""
    target = folder / name
    tmp = None
    try:
        with tempfile.NamedTemporaryFile(
            mode="wb", dir=folder, prefix=".reference-", delete=False,
        ) as file:
            tmp = Path(file.name)
            file.write(data)
            file.flush()
            os.fsync(file.fileno())
        if target.is_symlink():
            raise LocalReferenceError("Linked local reference content denied")
        try:
            os.link(tmp, target)  # atomic, fails if an old version exists
        except FileExistsError:
            if (target.is_symlink() or not target.is_file()
                    or target.read_bytes() != data):
                raise LocalReferenceError("Existing reference content mismatch") from None
    finally:
        if tmp is not None:
            tmp.unlink(missing_ok=True)


def _read_receipt(folder: Path, path: Path, *, series_id: str,
                  asset_id: str, kind: str, version: int,
                  specification_sha256: str) -> dict:
    if path.is_symlink() or not path.is_file() or path.stat().st_size > 2048:
        raise LocalReferenceError("Reference receipt integrity failed")
    try:
        doc = json.loads(path.read_text(encoding="utf-8"))
        sha = path.stem
        if (type(doc) is not dict or _SHA.fullmatch(sha) is None
                or doc.get("source_sha256") != sha
                or doc.get("series_id") != series_id
                or doc.get("asset_id") != asset_id
                or doc.get("kind") != kind
                or doc.get("version") != version
                or doc.get("specification_sha256") != specification_sha256
                or doc.get("rights_self_attested") is not True
                or doc.get("rights_independently_verified") is not False
                or doc.get("source_kind") != "operator_supplied_local_reference"
                or type(doc.get("png_sha256")) is not str
                or _SHA.fullmatch(doc["png_sha256"]) is None
                or type(doc.get("width")) is not int
                or type(doc.get("height")) is not int
                or not 1 <= doc["width"] <= MAX_PREVIEW_SIDE
                or not 1 <= doc["height"] <= MAX_PREVIEW_SIDE):
            raise ValueError("Invalid receipt fields")
        image = folder / (sha + ".png")
        if image.is_symlink() or not image.is_file():
            raise ValueError("Invalid stored reference")
        if not 100 <= image.stat().st_size <= MAX_STORED_BYTES:
            raise ValueError("Invalid stored reference size")
        data = image.read_bytes()
        if _sha(data) != doc["png_sha256"]:
            raise ValueError("Reference digest mismatch")
        with Image.open(io.BytesIO(data)) as preview:
            if preview.format != "PNG" or preview.size != (
                doc["width"], doc["height"],
            ) or preview.mode != "RGB":
                raise ValueError("Reference format mismatch")
            preview.verify()
        return {
            "source_sha256": sha, "png_sha256": doc["png_sha256"],
            "series_id": series_id, "asset_id": asset_id,
            "kind": kind, "version": version,
            "width": doc["width"], "height": doc["height"],
            "rights_self_attested": True,
            "rights_independently_verified": False,
            "paid_api_calls": 0, "png_bytes": data,
        }
    except (OSError, ValueError, TypeError, UnicodeError, KeyError,
            UnidentifiedImageError, Image.DecompressionBombError):
        raise LocalReferenceError("Reference receipt integrity failed") from None


def list_local_asset_references(
    db: Database, series_id: str, asset_id: str, root: Path,
) -> list[dict]:
    """Only show decoded and SHA-verified versions belonging to that DB asset."""
    asset = _asset_row(db, series_id, asset_id)
    folder = _owned_folder(root, series_id, asset_id)
    if not folder.exists():
        return []
    if not folder.is_dir():
        raise LocalReferenceError("Invalid reference directory")
    records = sorted(folder.glob("*.json"))
    if len(records) > 20:
        raise LocalReferenceError("Too many local references for asset version")
    spec_sha = _sha(asset["specification_json"].encode("utf-8"))
    return [
        _read_receipt(
            folder, file, series_id=series_id, asset_id=asset_id,
            kind=asset["kind"], version=asset["version"],
            specification_sha256=spec_sha,
        )
        for file in records
    ]


def stage_local_asset_reference(
    db: Database, series_id: str, asset_id: str, root: Path,
    *, filename: str, content: bytes, operator_attests_rights: bool,
) -> dict:
    """Append sanitized image for an existing immutable actor/scene/prop version.

    Store no original file or metadata. Never modify its asset spec or
    automatically mark a reference as an approved model reference frame.
    """
    asset = _asset_row(db, series_id, asset_id)
    if operator_attests_rights is not True:
        raise LocalReferenceError("Explicit reference usage rights attestation required")
    if (type(filename) is not str or not 1 <= len(filename) <= 255
            or Path(filename).suffix.lower() not in {".png", ".jpg", ".jpeg", ".webp"}
            or type(content) is not bytes
            or not 100 <= len(content) <= MAX_SOURCE_BYTES):
        raise LocalReferenceError("Unsupported reference type or upload size")
    cleaned, width, height, source_format = _canonical_png(content)
    expected_format = {
        ".png": "PNG", ".jpg": "JPEG", ".jpeg": "JPEG", ".webp": "WEBP",
    }[Path(filename).suffix.lower()]
    if source_format != expected_format:
        raise LocalReferenceError("Image bytes do not match declared extension")
    source_sha = _sha(content)
    image_sha = _sha(cleaned)
    folder = _owned_folder(root, series_id, asset_id)
    if folder.exists() and len(list(folder.glob("*.json"))) >= 20:
        # Re-import of identical original bytes is still idempotent.
        if not (folder / (source_sha + ".json")).is_file():
            raise LocalReferenceError("Reference gallery limited to 20 image versions")
    folder = _owned_folder(root, series_id, asset_id, create=True)
    receipt = {
        "source_sha256": source_sha,
        "png_sha256": image_sha,
        "series_id": series_id, "asset_id": asset_id,
        "kind": asset["kind"], "version": asset["version"],
        "specification_sha256": _sha(asset["specification_json"].encode("utf-8")),
        "width": width, "height": height,
        "source_kind": "operator_supplied_local_reference",
        "rights_self_attested": True, "rights_independently_verified": False,
    }
    try:
        _publish_immutable(folder, source_sha + ".png", cleaned)
        _publish_immutable(
            folder, source_sha + ".json",
            json.dumps(receipt, ensure_ascii=False, sort_keys=True).encode("utf-8"),
        )
        confirmed = _read_receipt(
            folder, folder / (source_sha + ".json"),
            series_id=series_id, asset_id=asset_id,
            kind=asset["kind"], version=asset["version"],
            specification_sha256=receipt["specification_sha256"],
        )
        return {k: v for k, v in confirmed.items() if k != "png_bytes"}
    except OSError:
        raise LocalReferenceError("Could not stage local reference") from None
