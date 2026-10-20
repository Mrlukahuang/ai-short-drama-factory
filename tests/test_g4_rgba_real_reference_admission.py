"""Real V1 PNG fixtures and synthetic alpha pixels through existing FND importer.

No model/network/DB writes. The immutable RGBA originals remain untouched.
"""
from __future__ import annotations

import hashlib
import io
from pathlib import Path

from PIL import Image

from drama_factory.pipeline.local_asset_references import _canonical_png
from drama_factory.pipeline.visual_media_admission import verify_png

ROOT = Path(__file__).resolve().parents[1] / "assets" / "citydiscount" / "v1"
SOURCE_DIGESTS = {
    "mascot_character_sheet_v1.png": (
        "9706eb126398d703e3750c4ac0ca0d296e618ae548ca05d5b1f9a3d99633bf92",
        (1536, 1024),
    ),
    "citydiscount_logo_v1.png": (
        "19a6202331db9853d384ddabd30fbdf738f139fd8721638eed54fde193011651",
        (1024, 1024),
    ),
}


def test_real_v1_rgba_files_get_distinct_rgb_png_and_fnd02_byte_verification(tmp_path):
    for name, (source_sha, expected_dimensions) in SOURCE_DIGESTS.items():
        original = (ROOT / name).read_bytes()
        assert hashlib.sha256(original).hexdigest() == source_sha
        with Image.open(io.BytesIO(original)) as image:
            assert image.size == expected_dimensions
            assert image.mode == "RGBA"
        out, w, h, kind = _canonical_png(original)
        assert kind == "PNG"
        assert max(w, h) <= 1024
        assert hashlib.sha256(out).hexdigest() != source_sha
        with Image.open(io.BytesIO(out)) as image:
            assert image.mode == "RGB" and image.format == "PNG"
            assert image.size == (w, h)
        # This is merely byte admission, NOT rights approval for an AI provider.
        path = tmp_path / (name + ".normalized.png")
        path.write_bytes(out)
        png_sha = hashlib.sha256(out).hexdigest()
        assert verify_png(path, png_sha) == out
        assert _canonical_png(original)[0] == out
        # Original RGBA stays unchanged after every import attempt.
        assert hashlib.sha256((ROOT / name).read_bytes()).hexdigest() == source_sha


def test_transparency_mattes_without_black_halo():
    raw = Image.new("RGBA", (128, 64), (0, 0, 0, 0))
    raw.putpixel((10, 10), (255, 0, 0, 255))
    raw.putpixel((20, 20), (0, 0, 0, 128))
    content = io.BytesIO()
    raw.save(content, "PNG")
    out, w, h, fmt = _canonical_png(content.getvalue())
    assert (w, h, fmt) == (128, 64, "PNG")
    with Image.open(io.BytesIO(out)) as normalized:
        assert normalized.mode == "RGB"
        assert normalized.getpixel((0, 0)) == (255, 255, 255)
        assert normalized.getpixel((10, 10)) == (255, 0, 0)
        # Alpha 128 over white: half-grey, not opaque black.
        assert normalized.getpixel((20, 20)) in ((127, 127, 127), (128, 128, 128))
