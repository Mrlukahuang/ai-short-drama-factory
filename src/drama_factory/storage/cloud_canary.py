"""One explicit private cloud upload/download canary with synthetic offline media.

Never imports or calls a generative model, does not expose a public API, and
will not contact R2/S3 unless the operator runs --live with multiple opt-ins.
Only ONE small, reviewed technical MP4 is uploaded per live run.
"""
from __future__ import annotations

import argparse
import json
import os
from contextlib import contextmanager
from pathlib import Path

from fastapi.testclient import TestClient

from drama_factory.api import create_app
from drama_factory.jobs.offline_worker import run_offline_production
from drama_factory.storage.cloud_objects import (
    CloudArtifactError, CloudTarget, FakeS3ArtifactClient,
    publish_cloud_artifact, restore_cloud_artifact,
)


@contextmanager
def _fake_only_flags():
    """Enable storage gates only while the injected client is guaranteed FakeS3."""
    keys = ("DRAMA_ENABLE_CLOUD_UPLOAD", "DRAMA_ENABLE_CLOUD_READ")
    old = {key: os.environ.get(key) for key in keys}
    try:
        for key in keys:
            os.environ[key] = "YES"
        yield
    finally:
        for key, value in old.items():
            if value is None:
                os.environ.pop(key, None)
            else:
                os.environ[key] = value


def run_private_cloud_canary(
    out: Path, target: CloudTarget, *, live: bool = False, client=None,
) -> dict:
    """Build a wholly-original 2s MP4 then prove upload and round-trip integrity."""
    if live:
        if os.getenv("DRAMA_CLOUD_SMOKE_CONFIRM") != "TEST_ONE_PRIVATE_CLOUD_MP4":
            raise CloudArtifactError("Manual cloud storage confirmation is required")
        if (
            os.getenv("DRAMA_ENABLE_CLOUD_UPLOAD") != "YES"
            or os.getenv("DRAMA_ENABLE_CLOUD_READ") != "YES"
        ):
            raise CloudArtifactError("Both cloud I/O permission gates are required")
        selected = client
    else:
        if client is not None and not isinstance(client, FakeS3ArtifactClient):
            raise CloudArtifactError("Offline canary accepts FakeS3ArtifactClient only")
        selected = client if client is not None else FakeS3ArtifactClient()
    root = Path(out).resolve()
    root.mkdir(parents=True, exist_ok=True)
    with TestClient(create_app(root / "db")) as app:
        project = app.post("/api/v1/projects", json={
            "title": "Cloud archive connectivity canary",
            "premise": "A synthetic original red ball rolling on a table",
        })
        project.raise_for_status()
        series = project.json()["series_id"]
        episode = app.post(f"/api/v1/projects/{series}/episodes", json={
            "title": "Canary", "episode_number": 1,
            "target_duration_seconds": 2,
            "shots": [
                {"shot_id": "S1", "duration_seconds": 1,
                 "visual_description": "Synthetic preview first shot", "dialogue": ["One"]},
                {"shot_id": "S2", "duration_seconds": 1,
                 "visual_description": "Synthetic preview second shot", "dialogue": ["Two"]},
            ],
        })
        episode.raise_for_status()
        production = app.post(
            f"/api/v1/episodes/{episode.json()['episode_id']}/productions"
        )
        production.raise_for_status()
        pid = production.json()["production_id"]
        for gate in ("approve-script", "approve-characters"):
            response = app.post(f"/api/v1/productions/{pid}/{gate}")
            response.raise_for_status()
        db = app.app.state.db
        reviewed = run_offline_production(
            db, pid, root / "working", store_root=root / "local-catalog",
        )
        artifact_id = reviewed["published_artifact_ids"][-1]
        assert len(reviewed["published_artifact_ids"]) == 3
        # The live mode is disabled unless the caller supplies both environment
        # opt-ins and the exact independent manual canary confirmation.
        if live:
            receipt = publish_cloud_artifact(
                db, artifact_id, root / "local-catalog", target,
                operator_approved=True, client=selected,
            )
            recovered = restore_cloud_artifact(
                db, receipt["id"], target, root / "recovered-catalog",
                operator_approved=True, client=selected,
            )
        else:
            with _fake_only_flags():
                receipt = publish_cloud_artifact(
                    db, artifact_id, root / "local-catalog", target,
                    operator_approved=True, client=selected,
                )
                recovered = restore_cloud_artifact(
                    db, receipt["id"], target, root / "recovered-catalog",
                    operator_approved=True, client=selected,
                )
        if receipt["sha256"] != recovered["sha256"] or not recovered["verified"]:
            raise CloudArtifactError("Canary upload/download verification failed")
        result = {
            "mode": "live" if live else "fake",
            "provider": target.provider,
            "bucket": target.bucket,
            "cloud_copy_id": receipt["id"],
            "object_key": receipt["object_key"],
            "source_sha256": receipt["sha256"],
            "restored_sha256": recovered["sha256"],
            "verified": recovered["verified"],
            "size_bytes": receipt["size_bytes"],
            "new_ai_model_generation_calls": 0,
            "actual_cloud_charge_usd": None,
            "signed_download_url_created": False,
        }
        (root / "canary-verification.json").write_text(
            json.dumps(result, indent=2, ensure_ascii=False), encoding="utf-8",
        )
        return result


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(
        description="Explicit R2/S3 private archive smoke test; FAKE by default"
    )
    parser.add_argument("--live", action="store_true", help="Use real R2/S3 storage")
    parser.add_argument("--provider", choices=("r2", "s3"), default="r2")
    parser.add_argument("--out", type=Path, default=Path("artifacts/cloud-canary"))
    args = parser.parse_args(argv)
    if args.provider == "r2":
        account = os.getenv("DRAMA_R2_ACCOUNT_ID")
        if not args.live and not account:
            account = "a" * 32
        target = CloudTarget(
            provider="r2",
            bucket=os.getenv("DRAMA_CLOUD_BUCKET", "synthetic-offline-test"),
            r2_account_id=account,
        )
    else:
        region = os.getenv("DRAMA_AWS_REGION", "ap-southeast-2")
        target = CloudTarget(
            provider="s3",
            bucket=os.getenv("DRAMA_CLOUD_BUCKET", "synthetic-offline-test"),
            region=region,
        )
    summary = run_private_cloud_canary(args.out, target, live=args.live)
    # No credentials, signed links, model task IDs or copyrighted source content.
    print(json.dumps(summary, ensure_ascii=False, sort_keys=True))


if __name__ == "__main__":
    main()
