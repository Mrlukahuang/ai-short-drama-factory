"""One-time local OAuth bootstrap for a private, user-owned Drive folder.

Run only on the operator's own computer. Secrets are never printed or written
inside the git repository by default. No video upload or model calls.
"""
from __future__ import annotations

import argparse
import json
import os
import re
from pathlib import Path

from drama_factory.storage.drive_objects import DRIVE_FILE_SCOPE, DriveArtifactError

FOLDER_NAME = "AI Short Drama Factory - Private Videos"
_FOLDER_ID = re.compile(r"[A-Za-z0-9_-]{8,160}")


def _persist_credentials(credentials, output: Path):
    """Refuse to overwrite existing token files, and write owner-only (0600)."""
    dest = Path(output).expanduser().resolve()
    dest.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
    if dest.is_symlink() or dest.exists():
        raise DriveArtifactError("OAuth output already exists; refusing overwrite")
    contents = credentials.to_json()
    values = json.loads(contents)
    if not values.get("refresh_token") or not values.get("client_id"):
        raise DriveArtifactError("No offline refresh token was granted")
    try:
        fd = os.open(dest, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
        with os.fdopen(fd, "w", encoding="utf-8") as file:
            file.write(contents)
            file.flush()
            os.fsync(file.fileno())
    except BaseException:
        dest.unlink(missing_ok=True)
        raise
    return dest


def authorize_drive(
    client_secrets: Path, output: Path, *,
    flow_factory=None, service_factory=None,
) -> dict:
    """User OAuth and one app-owned My Drive folder. Never print credentials."""
    client_path = Path(client_secrets).expanduser().resolve(strict=True)
    output_path = Path(output).expanduser().resolve()
    if output_path.exists() or output_path.is_symlink():
        raise DriveArtifactError("OAuth output already exists; refusing overwrite")
    if flow_factory is None:
        from google_auth_oauthlib.flow import InstalledAppFlow
        flow_factory = InstalledAppFlow.from_client_secrets_file
    flow = flow_factory(str(client_path), scopes=[DRIVE_FILE_SCOPE])
    credentials = flow.run_local_server(
        host="localhost", port=0, open_browser=True,
        access_type="offline", prompt="consent",
    )
    if not getattr(credentials, "refresh_token", None):
        raise DriveArtifactError("Google did not return a refresh token")
    if service_factory is None:
        from googleapiclient.discovery import build
        service_factory = build
    service = service_factory(
        "drive", "v3", credentials=credentials, cache_discovery=False,
    )
    query = (
        "name = '" + FOLDER_NAME + "' and 'root' in parents "
        "and mimeType = 'application/vnd.google-apps.folder' and trashed = false"
    )
    response = service.files().list(
        q=query, spaces="drive", page_size=10,
        fields="nextPageToken,files(id,name,mimeType,parents)",
    ).execute()
    matches = response.get("files", [])
    if response.get("nextPageToken") or len(matches) > 1:
        raise DriveArtifactError("Ambiguous root folder; manual review needed")
    if matches:
        folder = matches[0]
    else:
        # Omit parents to create one folder directly in My Drive. The OAuth
        # app itself owns access under drive.file, so no Picker is necessary.
        folder = service.files().create(
            body={
                "name": FOLDER_NAME,
                "mimeType": "application/vnd.google-apps.folder",
            },
            fields="id,name,mimeType,parents",
        ).execute()
    folder_id = folder.get("id", "")
    if (
        not _FOLDER_ID.fullmatch(folder_id)
        or folder.get("name") != FOLDER_NAME
        or folder.get("mimeType") != "application/vnd.google-apps.folder"
    ):
        raise DriveArtifactError("OAuth-created folder response is invalid")
    secured = _persist_credentials(credentials, output_path)
    return {
        "folder_id": folder_id,
        "credentials_path": str(secured),
        "scope": DRIVE_FILE_SCOPE,
        "uploaded_videos": 0,
    }


def main(argv=None) -> None:
    parser = argparse.ArgumentParser(description="Authorize private Google Drive uploads")
    parser.add_argument("--client-secrets", type=Path, required=True)
    parser.add_argument(
        "--output", type=Path,
        default=Path.home() / ".config/ai-short-drama-factory/drive-user-oauth.json",
    )
    args = parser.parse_args(argv)
    result = authorize_drive(args.client_secrets, args.output)
    print("Authorized a private Drive folder using drive.file.")
    print("Folder ID (not a password):", result["folder_id"])
    print("Private OAuth file saved at:", result["credentials_path"])
    print("Video files uploaded: 0")
    print("DO NOT paste the OAuth file contents into chat or commit it to git.")


if __name__ == "__main__":
    main()
