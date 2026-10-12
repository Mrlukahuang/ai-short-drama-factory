"""Read-only Turso canary cannot mutate DB, expose secrets, or run automatically."""
from __future__ import annotations

import os
import sqlite3
import subprocess
import sys
from pathlib import Path

import pytest

from drama_factory.storage.turso_receipts import (
    TursoMetadataTarget, TursoReceiptError,
)
from drama_factory.storage.turso_preflight import check_dedicated_turso, main, run_cli


TARGET = TursoMetadataTarget(
    url="libsql://ai-short-drama-factory-tests.turso.io", engine="libsql",
)


class ReadOnlyRemote:
    def __init__(self):
        self.db = sqlite3.connect(":memory:")
        self.calls = []

    def execute(self, sql, params=()):
        # Allow strictly SELECT queries only.
        assert sql.strip().upper().startswith("SELECT"), sql
        self.calls.append((sql, params))
        return self.db.execute(sql, params)

    def close(self):
        self.db.close()


def test_dry_run_refuses_to_connect_until_operator_approves(monkeypatch):
    monkeypatch.delenv("DRAMA_TURSO_READ_CONFIRM", raising=False)
    client = ReadOnlyRemote()
    with pytest.raises(TursoReceiptError, match="confirmation"):
        check_dedicated_turso(TARGET, operator_approved=True, remote=client)
    assert client.calls == []
    monkeypatch.setenv("DRAMA_TURSO_READ_CONFIRM", "CHECK_DEDICATED_DRAMA_DB")
    with pytest.raises(TursoReceiptError, match="confirmation"):
        check_dedicated_turso(TARGET, operator_approved=False, remote=client)
    assert client.calls == []


def test_turso_preflight_checks_only_selected_table_and_redacts(monkeypatch):
    monkeypatch.setenv("DRAMA_TURSO_READ_CONFIRM", "CHECK_DEDICATED_DRAMA_DB")
    db = ReadOnlyRemote()
    result = check_dedicated_turso(TARGET, operator_approved=True, remote=db)
    assert result == {
        "reachable": True,
        "engine": "libsql",
        "dedicated_name_validated": True,
        "metadata_table_exists": False,
        "read_only": True,
        "database_modified": False,
        "google_drive_operations": 0,
        "new_ai_model_generation_calls": 0,
    }
    assert len(db.calls) == 2
    assert "sqlite_master" in db.calls[1][0]
    assert db.calls[1][1] == ("drama_drive_receipts_v1",)
    assert "ai-short-drama-factory-tests.turso.io" not in str(result)
    assert "DRAMA_TURSO_AUTH_TOKEN" not in str(result)
    assert db.db.execute("SELECT COUNT(*) FROM sqlite_master WHERE type='table'").fetchone()[0] == 0


def test_preflight_accepts_regional_dashboard_hostname_read_only(monkeypatch):
    monkeypatch.setenv("DRAMA_TURSO_READ_CONFIRM", "CHECK_DEDICATED_DRAMA_DB")
    regional = TursoMetadataTarget(
        url="libsql://ai-short-drama-factory-mrlukahuang.aws-ap-southeast-2.turso.io",
        engine="libsql",
    )
    remote = ReadOnlyRemote()
    result = check_dedicated_turso(regional, operator_approved=True, remote=remote)
    assert result["reachable"] is True
    assert result["read_only"] is True
    assert result["database_modified"] is False
    assert len(remote.calls) == 2
    assert all(sql.startswith("SELECT") for sql, _ in remote.calls)
    remote.close()


def test_preflight_reports_existing_receipt_table_without_writing(monkeypatch):
    monkeypatch.setenv("DRAMA_TURSO_READ_CONFIRM", "CHECK_DEDICATED_DRAMA_DB")
    db = ReadOnlyRemote()
    db.db.execute("CREATE TABLE drama_drive_receipts_v1 (id TEXT)")
    db.db.commit()
    result = check_dedicated_turso(TARGET, operator_approved=True, remote=db)
    assert result["metadata_table_exists"] is True
    assert len(db.calls) == 2


def test_cli_requires_live_flag_and_fails_before_sdk_or_network(monkeypatch, capsys):
    monkeypatch.setenv("TURSO_DATABASE_URL", "libsql://ai-short-drama-factory-tests.turso.io")
    monkeypatch.setenv("DRAMA_TURSO_READ_CONFIRM", "CHECK_DEDICATED_DRAMA_DB")
    with pytest.raises(TursoReceiptError, match="--live"):
        main(["--engine", "libsql"])
    assert capsys.readouterr().out == ""


def test_secret_required_before_any_remote_connection(monkeypatch):
    monkeypatch.setenv("DRAMA_TURSO_READ_CONFIRM", "CHECK_DEDICATED_DRAMA_DB")
    monkeypatch.delenv("TURSO_AUTH_TOKEN", raising=False)
    with pytest.raises(TursoReceiptError, match="token missing"):
        check_dedicated_turso(TARGET, operator_approved=True)


def test_workflow_is_manual_only_and_has_no_db_write_or_drive_token():
    workflow = (
        Path(__file__).resolve().parents[1]
        / ".github/workflows/manual-turso-readonly.yml"
    ).read_text()
    assert "workflow_dispatch:" in workflow
    assert "pull_request:" not in workflow
    assert "\n  push:" not in workflow
    assert "contents: read" in workflow
    assert "CHECK_DEDICATED_DRAMA_DB" in workflow
    assert "secrets.DRAMA_TURSO_DATABASE_URL" in workflow
    assert "secrets.DRAMA_TURSO_AUTH_TOKEN" in workflow
    assert "turso-libsql" in workflow
    assert "turso-serverless" in workflow
    assert "storage.turso_preflight" in workflow
    assert "DRAMA_DRIVE_USER_OAUTH_JSON" not in workflow
    assert "GEMINI_API_KEY" not in workflow
    assert "MIRROR_VERIFIED_DRIVE_METADATA" not in workflow


def test_live_cli_redacts_sdk_exceptions_and_token(monkeypatch, capsys):
    import drama_factory.storage.turso_preflight as preflight

    marker = "SECRET_TOKEN_MUST_NOT_APPEAR_IN_LOGS"
    monkeypatch.setenv("TURSO_DATABASE_URL", "libsql://ai-short-drama-factory-tests.turso.io")
    monkeypatch.setenv("TURSO_AUTH_TOKEN", marker)
    monkeypatch.setenv("DRAMA_TURSO_READ_CONFIRM", "CHECK_DEDICATED_DRAMA_DB")

    def failing_open(_target, token):
        raise RuntimeError(f"SDK error: authorization failed with token={token}")

    monkeypatch.setattr(preflight, "_open_remote", failing_open)
    assert run_cli(["--engine", "libsql", "--live"]) == 1
    captured = capsys.readouterr()
    assert captured.out == ""
    assert "details redacted" in captured.err
    assert marker not in captured.err
    assert "authorization failed" not in captured.err
    assert "Traceback" not in captured.err


def test_live_cli_emits_successful_redacted_verification(monkeypatch, capsys):
    import json
    import drama_factory.storage.turso_preflight as preflight

    monkeypatch.setenv("TURSO_DATABASE_URL", "libsql://ai-short-drama-factory-tests.turso.io")
    monkeypatch.setenv("TURSO_AUTH_TOKEN", "test-only-token")
    monkeypatch.setenv("DRAMA_TURSO_READ_CONFIRM", "CHECK_DEDICATED_DRAMA_DB")
    monkeypatch.setattr(preflight, "_open_remote", lambda target, token: ReadOnlyRemote())

    assert run_cli(["--engine", "libsql", "--live"]) == 0
    captured = capsys.readouterr()
    result = json.loads(captured.out)
    assert result["reachable"] is True
    assert result["database_modified"] is False
    assert result["read_only"] is True
    assert "test-only-token" not in captured.out
    assert captured.err == ""


def test_readonly_preflight_imports_without_media_or_pillow_packages():
    """Exercise a fresh process where optional video/Pillow imports are forbidden."""
    script = """
import builtins
import os
import sqlite3

original_import = builtins.__import__

def forbid_media_imports(name, *args, **kwargs):
    if name == "drama_factory.storage.artifacts" or name == "PIL" or name.startswith("PIL."):
        raise ImportError("Optional media dependency unexpectedly loaded: " + name)
    return original_import(name, *args, **kwargs)

builtins.__import__ = forbid_media_imports

from drama_factory.storage.turso_preflight import check_dedicated_turso
from drama_factory.storage.turso_receipts import TursoMetadataTarget

os.environ["DRAMA_TURSO_READ_CONFIRM"] = "CHECK_DEDICATED_DRAMA_DB"
remote = sqlite3.connect(":memory:")
target = TursoMetadataTarget(
    url="libsql://ai-short-drama-factory-tests.aws-ap-southeast-2.turso.io",
    engine="libsql",
)
result = check_dedicated_turso(target, operator_approved=True, remote=remote)
assert result["reachable"] is True
assert result["read_only"] is True
assert result["database_modified"] is False
assert result["metadata_table_exists"] is False
remote.close()
"""
    result = subprocess.run(
        [sys.executable, "-c", script],
        capture_output=True,
        text=True,
        check=False,
        timeout=15,
    )
    assert result.returncode == 0, result.stderr
