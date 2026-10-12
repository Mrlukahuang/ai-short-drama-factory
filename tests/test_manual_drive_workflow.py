"""Fail closed if manual Drive workflow drifts to another provider's dependencies."""
from pathlib import Path


def test_private_drive_manual_workflow_uses_drive_sdk_and_no_auto_trigger():
    root = Path(__file__).resolve().parents[1]
    workflow = (root / ".github/workflows/private-google-drive-canary.yml").read_text()
    assert "workflow_dispatch:" in workflow
    assert "pull_request:" not in workflow
    assert "push:" not in workflow
    assert "python -m pip install -e '.[test,drive-storage]'" in workflow
    assert "cloud-s3" not in workflow
    assert "DRAMA_DRIVE_USER_OAUTH_JSON: ${{ secrets.DRAMA_DRIVE_USER_OAUTH_JSON }}" in workflow
    assert "DRAMA_DRIVE_PARENT_FOLDER_ID: ${{ secrets.DRAMA_DRIVE_PARENT_FOLDER_ID }}" in workflow
    assert "DRAMA_DRIVE_SMOKE_CONFIRM: UPLOAD_ONE_PRIVATE_TEST_MP4" in workflow
    assert "DRAMA_ENABLE_DRIVE_UPLOAD: 'YES'" in workflow
    assert "DRAMA_ENABLE_DRIVE_READ: 'YES'" in workflow
    assert 'inputs.confirmation == \'UPLOAD_ONE_PRIVATE_TEST_MP4\'' in workflow
    assert "python -m drama_factory.storage.drive_canary --live" in workflow
    assert "drive_file_id_redacted" in workflow
