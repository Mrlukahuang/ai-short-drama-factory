"""Manual, one-MP4 Google Drive canary; FakeDrive and offline FFmpeg by default.

There is no public Drive share, no paid model invocation, no automatic trigger.
Real Google Drive requires explicit manual confirmation and two env gates.
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
from drama_factory.storage.drive_objects import (
    DriveArtifactError, FakeDriveClient,
    publish_drive_artifact, restore_drive_artifact,
)


@contextmanager
def _fake_gates():
    keys = ("DRAMA_ENABLE_DRIVE_UPLOAD", "DRAMA_ENABLE_DRIVE_READ")
    old = {key: os.environ.get(key) for key in keys}
    try:
        for key in keys:
            os.environ[key] = "YES"
        yield
    finally:
        for key, previous in old.items():
            if previous is None:
                os.environ.pop(key, None)
            else:
                os.environ[key] = previous


def _live_authorized():
    if os.environ.get("DRAMA_DRIVE_SMOKE_CONFIRM") != "UPLOAD_ONE_PRIVATE_TEST_MP4":
        raise DriveArtifactError("Manual confirmation required before Google Drive I/O")
    if (
        os.environ.get("DRAMA_ENABLE_DRIVE_UPLOAD") != "YES"
        or os.environ.get("DRAMA_ENABLE_DRIVE_READ") != "YES"
    ):
        raise DriveArtifactError("Both Drive transfer gates are required")


def run_drive_canary(
    output: Path, *, parent_folder_id: str = "fakeDriveRoot0001",
    live: bool = False, client=None, on_verified=None,
) -> dict:
    if live:
        _live_authorized()
        if parent_folder_id == "fakeDriveRoot0001":
            raise DriveArtifactError("A real app-created Drive folder ID is required")
        selected = client
    else:
        if client is not None and not isinstance(client, FakeDriveClient):
            raise DriveArtifactError("Fake mode only accepts the in-memory Drive client")
        selected = client or FakeDriveClient()
    root = Path(output).resolve()
    root.mkdir(parents=True, exist_ok=True)
    with TestClient(create_app(root / "db")) as api:
        project = api.post("/api/v1/projects", json={
            "title": "Private Drive canary",
            "premise": "An original, synthetic test video, no human likeness",
        })
        project.raise_for_status()
        series = project.json()["series_id"]
        episode = api.post(f"/api/v1/projects/{series}/episodes", json={
            "title": "Synthetic sample", "episode_number": 1,
            "target_duration_seconds": 2,
            "shots": [
                {"shot_id": "S1", "duration_seconds": 1,
                 "visual_description": "Original ball on a table", "dialogue": ["One"]},
                {"shot_id": "S2", "duration_seconds": 1,
                 "visual_description": "The ball stops", "dialogue": ["Two"]},
            ],
        })
        episode.raise_for_status()
        production = api.post(
            f"/api/v1/episodes/{episode.json()['episode_id']}/productions"
        )
        production.raise_for_status()
        production_id = production.json()["production_id"]
        for gate in ("approve-script", "approve-characters"):
            reply = api.post(f"/api/v1/productions/{production_id}/{gate}")
            reply.raise_for_status()
        db = api.app.state.db
        generated = run_offline_production(
            db, production_id, root / "working",
            store_root=root / "local-stored",
        )
        chosen_artifact = generated["published_artifact_ids"][-1]
        if live:
            receipt = publish_drive_artifact(
                db, chosen_artifact, root / "local-stored",
                parent_folder_id, operator_approved=True, client=selected,
            )
            recovered = restore_drive_artifact(
                db, receipt["id"], root / "downloaded-stored",
                parent_folder_id, operator_approved=True, client=selected,
            )
        else:
            with _fake_gates():
                receipt = publish_drive_artifact(
                    db, chosen_artifact, root / "local-stored",
                    parent_folder_id, operator_approved=True, client=selected,
                )
                recovered = restore_drive_artifact(
                    db, receipt["id"], root / "downloaded-stored",
                    parent_folder_id, operator_approved=True, client=selected,
                )
        if receipt["sha256"] != recovered["sha256"] or not recovered["verified"]:
            raise DriveArtifactError("Drive canary hash round-trip failed")
        # PR-30c: allow one explicit caller-supplied metadata hook while the
        # temporary SQLite ledger and the verified recovered media still exist.
        # No hook is installed by the ordinary Drive-only canary.
        if on_verified is not None:
            on_verified(db, receipt["id"], root / "downloaded-stored")
        result = {
            "storage": "google-drive",
            "mode": "live" if live else "fake",
            "size_bytes": receipt["size_bytes"],
            "sha256_before": receipt["sha256"],
            "sha256_after": recovered["sha256"],
            "verified": True,
            "uploaded_mp4_count": 1,
            "new_ai_model_generation_calls": 0,
            "drive_file_id_redacted": True,
            "actual_drive_storage_charges_verified": False,
        }
        (root / "canary-verification.json").write_text(
            json.dumps(result, sort_keys=True, indent=2),
            encoding="utf-8",
        )
        return result


def main(argv=None) -> None:
    parser = argparse.ArgumentParser(
        description="Manually verify one synthetic MP4 round-trip to Google Drive"
    )
    parser.add_argument("--live", action="store_true")
    parser.add_argument("--out", type=Path, default=Path("artifacts/drive-canary"))
    args = parser.parse_args(argv)
    parent = (
        os.environ.get("DRAMA_DRIVE_PARENT_FOLDER_ID", "")
        if args.live else "fakeDriveRoot0001"
    )
    if args.live and not parent:
        raise DriveArtifactError("Private Drive folder ID is not configured")
    result = run_drive_canary(args.out, parent_folder_id=parent, live=args.live)
    print(json.dumps(result, sort_keys=True))


if __name__ == "__main__":
    main()
