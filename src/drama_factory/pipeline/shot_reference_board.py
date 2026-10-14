"""Human-selected, LOCAL shot reference board for draft continuity comparison.

All choices are pinned to the exact canonical Screenplay draft fingerprint.
This does NOT change Episode/Production state or authorize model transfers.
Only for trusted localhost development machines. No third-party bytes.
"""
from __future__ import annotations

import hashlib
import json
import os
import re
import tempfile
from pathlib import Path

from drama_factory.db import Database
from drama_factory.pipeline.local_asset_references import (
    LocalReferenceError, list_local_asset_references,
)
from drama_factory.pipeline.local_story_workflow import canonical_screenplay_digest
from drama_factory.pipeline.screenplay import (
    Screenplay, ScreenplayReferenceError, check_screenplay_scope,
)

_SERIES = re.compile(r"proj_[a-f0-9]{14}\Z")
_SHA = re.compile(r"[a-f0-9]{64}\Z")
_MAX_PROPS_PER_SHOT = 4


class LocalShotReferenceError(ValueError):
    """Never include operator photo bytes or private screenplay text in errors."""


def _validated(db: Database, draft: dict):
    try:
        screenplay = Screenplay.model_validate(draft)
        if (_SERIES.fullmatch(screenplay.series_id) is None
                or not 1 <= len(screenplay.shots) <= 12
                or screenplay.target_duration_seconds > 90):
            raise ValueError("Out of local storyboard bounds")
        check_screenplay_scope(db, screenplay)
        fingerprint = canonical_screenplay_digest(draft)
        return screenplay, fingerprint
    except (ValueError, TypeError, ScreenplayReferenceError):
        raise LocalShotReferenceError("Invalid or foreign local draft references") from None


def _folder(root: Path, series: str, fingerprint: str, *, create: bool = False):
    root = Path(root).absolute()
    folder = root / series / fingerprint
    if any(p.is_symlink() for p in (
        root.parent, root, root / series, folder,
    )):
        raise LocalShotReferenceError("Linked local shot reference path denied")
    if create:
        folder.mkdir(parents=True, exist_ok=True)
    return folder


def _shot_receipt(folder: Path, shot_id: str) -> Path:
    if type(shot_id) is not str or not 1 <= len(shot_id) <= 80:
        raise LocalShotReferenceError("Invalid shot ID")
    return folder / (hashlib.sha256(shot_id.encode("utf-8")).hexdigest() + ".json")


def _allowed(db: Database, series: str, shot, selected: dict[str, str]) -> None:
    if (type(selected) is not dict or len(selected) > 13
            or any(type(a) is not str or type(h) is not str
                   or _SHA.fullmatch(h) is None for a, h in selected.items())):
        raise LocalShotReferenceError("Invalid shot reference choices")
    if sum(1 for asset in selected if asset not in shot.character_ids
           and asset != shot.scene_id) > _MAX_PROPS_PER_SHOT:
        raise LocalShotReferenceError("Too many optional prop references")
    for asset_id in selected:
        row = db.one(
            "SELECT kind FROM series_assets WHERE id=? AND series_id=?",
            (asset_id, series),
        )
        if row is None:
            raise LocalShotReferenceError("Foreign asset selection denied")
        if asset_id in shot.character_ids:
            expected = "actor"
        elif shot.scene_id and asset_id == shot.scene_id:
            expected = "scene"
        else:
            expected = "prop"  # Props are human annotations, not screenplay references.
        if row["kind"] != expected:
            raise LocalShotReferenceError("Shot asset has incompatible type")


def _verified_images(db: Database, series: str, selected: dict[str, str],
                     image_root: Path) -> list[dict]:
    verified = []
    for asset_id, source_sha in sorted(selected.items()):
        try:
            matches = [
                item for item in list_local_asset_references(
                    db, series, asset_id, image_root,
                ) if item["source_sha256"] == source_sha
            ]
        except (LocalReferenceError, OSError):
            raise LocalShotReferenceError("Shot reference image verification failed") from None
        if len(matches) != 1:
            raise LocalShotReferenceError("Selected reference image not available")
        item = matches[0]
        verified.append({
            "asset_id": asset_id,
            "asset_kind": item["kind"],
            "asset_version": item["version"],
            "source_sha256": source_sha,
            "png_sha256": item["png_sha256"],
            "png_bytes": item["png_bytes"],
            "width": item["width"],
            "height": item["height"],
            "rights_independently_verified": False,
        })
    return verified


def save_shot_reference_selection(
    db: Database, draft: dict, shot_id: str,
    selection: dict[str, str], image_root: Path, binding_root: Path,
    *, operator_confirmed: bool,
) -> dict:
    """Explicitly save/replace THIS shot's choice for THIS draft fingerprint.

    Absence of choices means clear the shot's references on explicit Apply.
    Does not modify the immutable uploaded images, approved screenplay, or DB.
    """
    screenplay, fingerprint = _validated(db, draft)
    if operator_confirmed is not True:
        raise LocalShotReferenceError("Human shot reference confirmation required")
    shot = next((s for s in screenplay.shots if s.shot_id == shot_id), None)
    if shot is None:
        raise LocalShotReferenceError("Unknown shot in selected draft")
    _allowed(db, screenplay.series_id, shot, selection)
    images = _verified_images(db, screenplay.series_id, selection, image_root)
    receipt = {
        "schema": "local-shot-reference-v1",
        "series_id": screenplay.series_id,
        "screenplay_fingerprint": fingerprint,
        "shot_id": shot_id,
        "selection": dict(sorted(selection.items())),
        "operator_selected": True,
        "model_use_approved": False,
        "publication_approved": False,
        "paid_api_calls": 0,
    }
    folder = _folder(binding_root, screenplay.series_id, fingerprint, create=True)
    destination = _shot_receipt(folder, shot_id)
    if destination.is_symlink():
        raise LocalShotReferenceError("Linked local shot receipt denied")
    temporary = None
    try:
        with tempfile.NamedTemporaryFile(
            mode="w", encoding="utf-8", dir=folder,
            prefix=".shotref-", suffix=".json", delete=False,
        ) as f:
            temporary = Path(f.name)
            json.dump(receipt, f, sort_keys=True, ensure_ascii=False)
            f.flush()
            os.fsync(f.fileno())
        os.replace(temporary, destination)
    except OSError:
        raise LocalShotReferenceError("Could not save local shot reference") from None
    finally:
        if temporary is not None:
            temporary.unlink(missing_ok=True)
    return {
        "shot_id": shot_id, "screenplay_fingerprint": fingerprint,
        "selection_count": len(images), "human_choice_recorded": True,
        "model_use_approved": False, "publication_approved": False,
        "paid_api_calls": 0,
    }


def build_shot_reference_board(db: Database, draft: dict, image_root: Path,
                               binding_root: Path) -> dict:
    """Read-only exact-draft board; reverify EVERY selected source on readback."""
    screenplay, fingerprint = _validated(db, draft)
    folder = _folder(binding_root, screenplay.series_id, fingerprint)
    shots = []
    for shot in screenplay.shots:
        receipt = _shot_receipt(folder, shot.shot_id)
        selected = {}
        if receipt.exists() or receipt.is_symlink():
            try:
                if (receipt.is_symlink() or not receipt.is_file()
                        or receipt.stat().st_size > 4096):
                    raise ValueError("Invalid receipt file")
                row = json.loads(receipt.read_text("utf-8"))
                if (type(row) is not dict or row.get("schema") != "local-shot-reference-v1"
                        or row.get("series_id") != screenplay.series_id
                        or row.get("screenplay_fingerprint") != fingerprint
                        or row.get("shot_id") != shot.shot_id
                        or row.get("operator_selected") is not True
                        or row.get("model_use_approved") is not False
                        or row.get("publication_approved") is not False
                        or row.get("paid_api_calls") != 0):
                    raise ValueError("Invalid receipt scope")
                selected = row["selection"]
                _allowed(db, screenplay.series_id, shot, selected)
            except (OSError, ValueError, TypeError, KeyError, UnicodeError):
                raise LocalShotReferenceError("Stored shot reference scope invalid") from None
        images = _verified_images(db, screenplay.series_id, selected, image_root)
        shots.append({
            "shot_id": shot.shot_id,
            "actor_ids": list(shot.character_ids),
            "scene_id": shot.scene_id,
            "reference_images": images,
            "reference_selection": selected,
            "explicitly_selected": bool(selected),
        })
    issues = []
    for previous, current in zip(shots, shots[1:]):
        left = previous["reference_selection"]
        right = current["reference_selection"]
        same_actors = set(previous["actor_ids"]) & set(current["actor_ids"])
        same_scene = (
            {previous["scene_id"]}
            if previous["scene_id"] and previous["scene_id"] == current["scene_id"]
            else set()
        )
        # Only compare the SAME asset version used in both adjacent shots,
        # plus prop IDs explicitly selected in either shot.
        shared = same_actors | same_scene
        props = {img["asset_id"] for shot in (previous, current)
                 for img in shot["reference_images"] if img["asset_kind"] == "prop"}
        for asset in sorted(shared | (props & (set(left) | set(right)))):
            a, b = left.get(asset), right.get(asset)
            if a == b and a is not None:
                continue
            if a is None and b is None:
                continue
            kind = "different_reference" if a is not None and b is not None else "missing_reference"
            issues.append({
                "from_shot": previous["shot_id"], "to_shot": current["shot_id"],
                "asset_id": asset, "kind": kind,
                "message": ("相邻镜头对同一资产版本选用了不同参考图，请人工确认是否正常换装/转场"
                            if kind == "different_reference"
                            else "同一资产版本仅一侧镜头选择了参考图，请人工检查"),
            })
    return {
        "kind": "local_draft_shot_reference_board",
        "series_id": screenplay.series_id, "screenplay_fingerprint": fingerprint,
        "shots": shots, "review_prompts": issues,
        "review_required": True, "approval_granted": False,
        "model_use_approved": False, "publication_approved": False,
        "paid_api_calls": 0,
    }
