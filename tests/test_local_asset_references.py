"""Offline asset reference: real Pillow decoding, sanitization and scoped gallery.

Synthetic drawings only; no real face, novel, copyrighted image or model call.
"""
from __future__ import annotations

import ast
from copy import deepcopy
import io
import json
from pathlib import Path

from PIL import Image
import pytest

from drama_factory.pipeline.local_asset_references import (
    LocalReferenceError, MAX_SOURCE_BYTES,
    stage_local_asset_reference, list_local_asset_references,
)
from test_screenplay import setup_series


def sample_image(*, kind="PNG", color=(20, 105, 182), size=(1200, 900),
                 metadata=False) -> bytes:
    picture = Image.new("RGB", size, color)
    out = io.BytesIO()
    if kind == "JPEG" and metadata:
        exif = Image.Exif()
        exif[0x0112] = 1  # orientation
        exif[270] = "private-test-origin-location"
        picture.save(out, format=kind, exif=exif)
    else:
        picture.save(out, format=kind)
    return out.getvalue()


def setup(client, tmp_path):
    series, _, actor, scene = setup_series(client, "Local references")
    return client.app.state.db, series, actor, scene, tmp_path / "refs"


def stage(db, series, asset, root, data, *, filename="ref.png", rights=True):
    return stage_local_asset_reference(
        db, series, asset, root, filename=filename, content=data,
        operator_attests_rights=rights,
    )


def test_actor_reference_is_sanitized_and_tied_to_exact_version(client, tmp_path):
    db, series, actor, scene, root = setup(client, tmp_path)
    original = sample_image(kind="JPEG", metadata=True)
    created = stage(db, series, actor, root, original, filename="portrait.jpg")
    assert created["kind"] == "actor"
    assert created["asset_id"] == actor
    assert created["version"] == 1
    assert created["width"] == 1024
    assert created["height"] == 768
    assert created["rights_self_attested"] is True
    assert created["rights_independently_verified"] is False
    assert created["paid_api_calls"] == 0
    gallery = list_local_asset_references(db, series, actor, root)
    assert len(gallery) == 1
    assert gallery[0]["png_sha256"] == created["png_sha256"]
    stored = gallery[0]["png_bytes"]
    assert b"private-test-origin-location" not in stored
    assert original not in stored
    with Image.open(io.BytesIO(stored)) as image:
        assert image.format == "PNG"
        assert image.mode == "RGB"
        assert image.size == (1024, 768)
        assert "exif" not in image.info
    assert list_local_asset_references(db, series, scene, root) == []
    assert db.one("SELECT version FROM series_assets WHERE id=?", (actor,))["version"] == 1


def test_idempotent_upload_and_new_reference_are_append_only(client, tmp_path):
    db, series, actor, _, root = setup(client, tmp_path)
    first = sample_image(color=(42, 70, 90))
    second = sample_image(color=(112, 15, 96))
    x = stage(db, series, actor, root, first)
    y = stage(db, series, actor, root, first)
    assert x == y
    assert len(list_local_asset_references(db, series, actor, root)) == 1
    stage(db, series, actor, root, second)
    entries = list_local_asset_references(db, series, actor, root)
    assert len(entries) == 2
    assert set(e["source_sha256"] for e in entries) == {
        x["source_sha256"], __import__("hashlib").sha256(second).hexdigest(),
    }
    assert len(list((root / series / actor).glob("*.png"))) == 2


def test_new_asset_version_cannot_inherit_old_image(client, tmp_path):
    db, series, actor, _, root = setup(client, tmp_path)
    data = sample_image()
    stage(db, series, actor, root, data)
    new_actor = client.post(f"/api/v1/series/{series}/assets", json={
        "kind": "actor", "key": "female",
        "specification": {
            "name": "女主", "appearance": "短发与红色外套",
            "identity_anchors": ["眼角有痣"],
        },
    })
    assert new_actor.status_code == 201, new_actor.text
    new_id = new_actor.json()["asset_id"]
    assert new_actor.json()["version"] == 2
    assert list_local_asset_references(db, series, new_id, root) == []
    assert len(list_local_asset_references(db, series, actor, root)) == 1
    stage(db, series, new_id, root, data)
    assert len(list_local_asset_references(db, series, new_id, root)) == 1


def test_cross_series_cross_asset_and_voice_refused_before_disk_writes(client, tmp_path):
    db, series, actor, _, root = setup(client, tmp_path)
    other, _, foreign_actor, _ = setup_series(client, "Other series")
    img = sample_image()
    with pytest.raises(LocalReferenceError, match="not found"):
        stage(db, series, foreign_actor, root, img)
    with pytest.raises(LocalReferenceError, match="not found"):
        stage(db, other, actor, root, img)
    with pytest.raises(LocalReferenceError, match="selection"):
        stage(db, "../" + series, actor, root, img)
    voice = client.post(f"/api/v1/series/{series}/assets", json={
        "kind": "voice", "key": "voice", "specification": {
            "name": "虚构声音", "voice_description": "低沉语气",
        },
    })
    assert voice.status_code == 201
    voice_id = voice.json()["asset_id"]
    with pytest.raises(LocalReferenceError, match="not found"):
        stage(db, series, voice_id, root, img)
    assert not root.exists()


def test_attestation_extension_and_malformed_images_fail_before_writes(client, tmp_path):
    db, series, actor, _, root = setup(client, tmp_path)
    img = sample_image()
    with pytest.raises(LocalReferenceError, match="attestation"):
        stage(db, series, actor, root, img, rights=False)
    with pytest.raises(LocalReferenceError, match="type"):
        stage(db, series, actor, root, img, filename="bad.svg")
    with pytest.raises(LocalReferenceError, match="bytes"):
        stage(db, series, actor, root, img, filename="bad.jpg")
    with pytest.raises(LocalReferenceError, match="Invalid"):
        stage(db, series, actor, root, b"fake image" * 60)
    with pytest.raises(LocalReferenceError, match="size"):
        stage(db, series, actor, root, b"n" * (MAX_SOURCE_BYTES + 1))
    assert not root.exists()


def test_oversized_dimensions_and_animation_denied(client, tmp_path):
    db, series, actor, _, root = setup(client, tmp_path)
    giant = sample_image(size=(4097, 2))
    with pytest.raises(LocalReferenceError):
        stage(db, series, actor, root, giant)
    animated = io.BytesIO()
    im = Image.new("RGB", (32, 32))
    im.save(animated, format="WEBP", save_all=True,
            append_images=[Image.new("RGB", (32, 32), "red")],
            duration=100, loop=0)
    with pytest.raises(LocalReferenceError):
        stage(db, series, actor, root, animated.getvalue(), filename="anim.webp")
    assert not root.exists()


def test_reference_receipt_and_image_tampering_are_fail_closed(client, tmp_path):
    db, series, actor, _, root = setup(client, tmp_path)
    img = sample_image()
    stage(db, series, actor, root, img)
    folder = root / series / actor
    receipt = next(folder.glob("*.json"))
    image = next(folder.glob("*.png"))
    old = receipt.read_bytes()
    try:
        payload = json.loads(old)
        payload["version"] = 123
        receipt.write_text(json.dumps(payload), encoding="utf-8")
        with pytest.raises(LocalReferenceError, match="integrity"):
            list_local_asset_references(db, series, actor, root)
    finally:
        receipt.write_bytes(old)
    original = image.read_bytes()
    image.write_bytes(b"tampered")
    with pytest.raises(LocalReferenceError, match="integrity"):
        list_local_asset_references(db, series, actor, root)
    image.write_bytes(original)
    assert len(list_local_asset_references(db, series, actor, root)) == 1


def test_symlinked_root_receipt_and_image_denied(client, tmp_path):
    db, series, actor, _, root = setup(client, tmp_path)
    stage(db, series, actor, root, sample_image())
    folder = root / series / actor
    receipt = next(folder.glob("*.json"))
    source = receipt.with_suffix(".backup")
    receipt.rename(source)
    try:
        receipt.symlink_to(source)
        with pytest.raises(LocalReferenceError, match="integrity"):
            list_local_asset_references(db, series, actor, root)
        with pytest.raises(LocalReferenceError, match="content"):
            stage(db, series, actor, root, sample_image())
    finally:
        receipt.unlink()
        source.rename(receipt)
    link = tmp_path / "linked"
    link.symlink_to(root, target_is_directory=True)
    with pytest.raises(LocalReferenceError, match="Linked"):
        list_local_asset_references(db, series, actor, link)
    assert len(list_local_asset_references(db, series, actor, root)) == 1


def test_asset_reference_gallery_streamlit_code_compiles():
    root = Path(__file__).resolve().parents[1]
    for name in ("frontend/asset_reference_gallery.py", "frontend/app.py"):
        ast.parse((root / name).read_text("utf-8"), filename=name)
