"""Manual one-image test. Default is offline. Paid mode is one SDK request, no retries."""
from __future__ import annotations

import argparse
import json
from pathlib import Path
from tempfile import TemporaryDirectory

from drama_factory.db import DEFAULT_COLUMN_ID, Database, new_id, timestamp
from drama_factory.providers.google_image import (
    FakeGoogleImageProvider, GoogleImageProvider, GoogleImageSpec,
)

PORTRAIT_PROMPT = (
    "Cinematic photorealistic casting portrait of one fictional adult "
    "East Asian woman, age around 30. Neutral gray studio background; "
    "short dark hair, distinct small beauty mark under her left eye, "
    "natural face proportions, charcoal jacket; non-celebrity, original "
    "identity, vertical 9:16, clean studio lighting, detailed texture, "
    "no text and no logos."
)


def run_smoke(
    *,
    paid: bool = False,
    out_dir: Path | None = None,
    provider=None,
) -> dict:
    """Run once, only after explicit opt-in. No model calls by default."""
    with TemporaryDirectory(prefix="drama-image-smoke-") as tmp:
        db = Database(Path(tmp) / "factory.sqlite3")
        series_id = new_id("proj")
        actor_id = new_id("asset")
        db.exec(
            """INSERT INTO projects
            (id,title,premise,visual_style,ratio,created_at,column_id)
            VALUES (?,?,?,?,?,?,?)""",
            (
                series_id, "Manual single-image smoke", "fictional casting only",
                "live_action", "9:16", timestamp(), DEFAULT_COLUMN_ID,
            ),
        )
        db.exec(
            """INSERT INTO series_assets
            (id,series_id,kind,asset_key,version,specification_json,created_at)
            VALUES (?,?,?,?,?,?,?)""",
            (
                actor_id, series_id, "actor", "fictional_female_lead", 1,
                Database.to_json({
                    "name": "Fictional Lead",
                    "appearance": "short dark hair, adult",
                    "identity_anchors": ["small beauty mark beneath left eye"],
                }),
                timestamp(),
            ),
        )
        spec = GoogleImageSpec(
            series_id=series_id,
            actor_asset_id=actor_id,
            prompt=PORTRAIT_PROMPT,
            maximum_acknowledged_spend_usd="1.00",
            operator_approved=paid,
        )
        selected = provider or (GoogleImageProvider() if paid else FakeGoogleImageProvider())
        result = selected.generate(db, spec)
        if result.is_mock:
            if paid:
                raise ValueError("Paid smoke test must not return a fake image")
            return {
                "mode": "dry-run",
                "is_mock": True,
                "paid_model_calls": 0,
                "image_created": False,
            }
        if not paid:
            raise ValueError("Dry-run must not create or charge for a real image")
        if not result.jpeg_bytes:
            raise ValueError("Paid provider did not return image bytes")
        location = (out_dir or Path("artifacts")) / "smoke_fictional_actor.jpg"
        location.parent.mkdir(parents=True, exist_ok=True)
        location.write_bytes(result.jpeg_bytes)
        return {
            "mode": "paid-manual",
            "is_mock": False,
            "paid_model_calls": result.paid_model_calls,
            "model": result.model_id,
            "image_path": str(location),
            "image_sha256": result.sha256,
        }


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(description="One controlled Google actor image smoke test")
    parser.add_argument(
        "--paid", action="store_true",
        help="Make exactly one paid Google image request; requires independent safety gates",
    )
    parser.add_argument("--out", type=Path, default=Path("artifacts"))
    args = parser.parse_args(argv)
    outcome = run_smoke(paid=args.paid, out_dir=args.out)
    print(json.dumps(outcome, ensure_ascii=False, sort_keys=True))


if __name__ == "__main__":
    main()
