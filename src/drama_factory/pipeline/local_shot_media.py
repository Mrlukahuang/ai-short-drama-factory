"""Local operator-supplied shot video ingest, scoped to an approved run.

No public upload endpoint, cloud calls, automatic media rights claims or
publication. Streamlit only: videos stay on the same trusted local machine.
"""
from __future__ import annotations

import hashlib
import json
import os
import re
import tempfile
from pathlib import Path

from drama_factory.db import Database
from drama_factory.models import EpisodeDraft
from drama_factory.pipeline.media_ingest import EXTENSIONS, MediaIngressError, inspect_source

MAX_UPLOAD_BYTES = 32 * 1024 * 1024
_ALLOWED_STATUS = {"ready_for_video_generation", "offline_preview_finished"}
_ID = re.compile(r"(?:proj|run)_[a-f0-9]{14}\Z")
_SHA = re.compile(r"[a-f0-9]{64}\Z")


class LocalShotMediaError(ValueError):
    """Fixed operator-facing errors: no source paths/private video content."""


def _scope(db: Database, series_id: str, production_id: str) -> EpisodeDraft:
    if (
        type(series_id) is not str or type(production_id) is not str
        or not _ID.fullmatch(series_id) or not _ID.fullmatch(production_id)
        or not series_id.startswith("proj_") or not production_id.startswith("run_")
    ):
        raise LocalShotMediaError("Invalid local production selection")
    row = db.one(
        """SELECT e.project_id, e.body_json, p.status FROM productions p
           JOIN episodes e ON e.id=p.episode_id WHERE p.id=?""",
        (production_id,),
    )
    if row is None or row["project_id"] != series_id or row["status"] not in _ALLOWED_STATUS:
        raise LocalShotMediaError("Production must belong to series and pass both approvals")
    try:
        draft = EpisodeDraft.model_validate_json(row["body_json"])
        if not 1 <= len(draft.shots) <= 12 or draft.target_duration_seconds > 90:
            raise ValueError("Preview size exceeds local limits")
        return draft
    except (ValueError, TypeError):
        raise LocalShotMediaError("Invalid approved episode") from None


def _folder(root: Path, series_id: str, production_id: str, *, create: bool) -> Path:
    root = Path(root).absolute()
    path = root / series_id / production_id
    # Never follow symlinks in operator-configured roots or owned workspace.
    if any(p.is_symlink() for p in (
        root.parent, root, root / series_id, path,
    )):
        raise LocalShotMediaError("Linked local media workspace denied")
    if create:
        path.mkdir(parents=True, exist_ok=True)
    return path


def _receipt_path(folder: Path, shot_id: str) -> Path:
    if type(shot_id) is not str or not 1 <= len(shot_id) <= 80:
        raise LocalShotMediaError("Invalid selected shot")
    return folder / ("shot_" + hashlib.sha256(shot_id.encode("utf-8")).hexdigest() + ".json")


def _digest(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as fp:
        for chunk in iter(lambda: fp.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def _load_receipt(folder: Path, shot_id: str, series: str, production: str,
                  duration: int) -> dict | None:
    receipt = _receipt_path(folder, shot_id)
    if not receipt.exists() and not receipt.is_symlink():
        return None
    if receipt.is_symlink() or not receipt.is_file() or receipt.stat().st_size > 2048:
        raise LocalShotMediaError("Untrusted local shot media receipt")
    try:
        doc = json.loads(receipt.read_text("utf-8"))
        if (
            type(doc) is not dict or doc.get("shot_id") != shot_id
            or doc.get("series_id") != series
            or doc.get("production_id") != production
            or doc.get("rights_self_attested") is not True
            or type(doc.get("sha256")) is not str
            or _SHA.fullmatch(doc["sha256"]) is None
            or doc.get("extension") not in EXTENSIONS
            or type(doc.get("size_bytes")) is not int
            or not 1000 <= doc["size_bytes"] <= MAX_UPLOAD_BYTES
        ):
            raise ValueError("receipt values")
        media = folder / ("media_" + doc["sha256"] + doc["extension"])
        if (media.is_symlink() or not media.is_file()
                or media.stat().st_size != doc["size_bytes"]
                or _digest(media) != doc["sha256"]):
            raise ValueError("media bytes")
        # Inspect again on each use, not only at ingest; checks codec and
        # duration to prevent prior receipt being treated as media approval.
        info = inspect_source(media, duration)
        if info["sha256"] != doc["sha256"]:
            raise ValueError("inspected media hash")
        return {"path": media, "sha256": doc["sha256"],
                "size_bytes": doc["size_bytes"], "duration": info["duration"],
                "rights_self_attested": True}
    except (ValueError, TypeError, KeyError, OSError, UnicodeError,
            MediaIngressError):
        raise LocalShotMediaError("Local shot video failed readback integrity check") from None


def stage_local_shot_video(
    db: Database, production_id: str, series_id: str, root: Path,
    *, shot_id: str, filename: str, content: bytes,
    operator_attests_rights: bool,
) -> dict:
    """Stage immutable video bytes and atomically bind them to one shot.

    Sidecar is replaceable only through another explicit operator operation.
    This DOES NOT claim that commercial/publication rights were verified.
    """
    episode = _scope(db, series_id, production_id)
    shots = {s.shot_id: s for s in episode.shots}
    if type(shot_id) is not str or shot_id not in shots:
        raise LocalShotMediaError("Selected shot does not belong to production")
    if operator_attests_rights is not True:
        raise LocalShotMediaError("Explicit local media rights attestation required")
    if (
        type(filename) is not str or not 1 <= len(filename) <= 255
        or type(content) is not bytes
        or not 1000 <= len(content) <= MAX_UPLOAD_BYTES
    ):
        raise LocalShotMediaError("Invalid upload name or size")
    suffix = Path(filename).suffix.lower()
    if suffix not in EXTENSIONS:
        raise LocalShotMediaError("Unsupported local video extension")
    folder = _folder(root, series_id, production_id, create=True)
    source_sha = hashlib.sha256(content).hexdigest()
    saved = folder / ("media_" + source_sha + suffix)
    temp: Path | None = None
    try:
        with tempfile.NamedTemporaryFile(
            mode="wb", dir=folder, prefix=".ingest-", suffix=suffix, delete=False
        ) as out:
            temp = Path(out.name)
            out.write(content)
            out.flush()
            os.fsync(out.fileno())
        inspected = inspect_source(temp, shots[shot_id].duration_seconds)
        if inspected["sha256"] != source_sha:
            raise LocalShotMediaError("Uploaded bytes changed during local inspection")
        if saved.is_symlink():
            raise LocalShotMediaError("Linked local media source denied")
        if saved.exists():
            if not saved.is_file() or saved.stat().st_size != len(content) or _digest(saved) != source_sha:
                raise LocalShotMediaError("Conflicting local media content")
        else:
            # Atomic file creation without overwriting an existing target.
            try:
                os.link(temp, saved)
            except FileExistsError:
                if saved.is_symlink() or not saved.is_file() or _digest(saved) != source_sha:
                    raise LocalShotMediaError("Conflicting concurrent media content") from None
        info = {
            "shot_id": shot_id, "series_id": series_id,
            "production_id": production_id, "sha256": source_sha,
            "extension": suffix, "size_bytes": len(content),
            "rights_self_attested": True,
        }
        receipt = _receipt_path(folder, shot_id)
        if receipt.is_symlink():
            raise LocalShotMediaError("Linked local media receipt denied")
        with tempfile.NamedTemporaryFile(
            mode="w", encoding="utf-8", dir=folder,
            prefix=".receipt-", suffix=".json", delete=False
        ) as out:
            temp_receipt = Path(out.name)
            try:
                json.dump(info, out, ensure_ascii=False, sort_keys=True)
                out.flush()
                os.fsync(out.fileno())
            finally:
                pass
        try:
            os.replace(temp_receipt, receipt)
        finally:
            temp_receipt.unlink(missing_ok=True)
        verified = _load_receipt(
            folder, shot_id, series_id, production_id,
            shots[shot_id].duration_seconds,
        )
        assert verified is not None
        return {"shot_id": shot_id, "sha256": source_sha,
                "size_bytes": len(content), "duration": verified["duration"],
                "rights_self_attested": True, "rights_independently_verified": False,
                "paid_api_calls": 0}
    except (MediaIngressError, OSError) as exc:
        raise LocalShotMediaError("Local video ingest failed validation") from None
    finally:
        if temp is not None:
            temp.unlink(missing_ok=True)


def get_staged_shot_clips(
    db: Database, production_id: str, series_id: str, root: Path,
) -> dict[str, Path]:
    """Read verified scoped shot receipts, for passing to existing renderer.

    No DB mutations, no network requests. Any corrupt receipt blocks ALL
    local-source rendering rather than silently falling back to placeholders.
    """
    episode = _scope(db, series_id, production_id)
    folder = _folder(root, series_id, production_id, create=False)
    result: dict[str, Path] = {}
    for shot in episode.shots:
        entry = _load_receipt(
            folder, shot.shot_id, series_id, production_id, shot.duration_seconds,
        )
        if entry is not None:
            result[shot.shot_id] = entry["path"]
    return result
