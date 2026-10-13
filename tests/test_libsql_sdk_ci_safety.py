"""Never let the real-SDK CI job accidentally gain remote DB credentials."""
from __future__ import annotations

from pathlib import Path


def test_pinned_libsql_ci_job_is_local_only_and_never_injects_secrets():
    workflow = (
        Path(__file__).resolve().parents[1] / ".github/workflows/ci.yml"
    ).read_text()
    assert "  libsql-sdk-local:" in workflow
    before, rest = workflow.split("  libsql-sdk-local:", 1)
    local_job, after = rest.split("  offline-video:", 1)
    assert "python -m pip install 'libsql==0.1.11'" in local_job
    assert "pytest -q tests/test_libsql_sdk_local_only.py -rs" in local_job
    assert "import libsql" in local_job
    assert "DRAMA_FACTORY_OFFLINE: '1'" in local_job
    assert "DRAMA_TXLAB_DATABASE_URL: ''" in local_job
    assert "DRAMA_TXLAB_AUTH_TOKEN: ''" in local_job
    assert "secrets." not in local_job
    assert "workflow_dispatch:" not in local_job
    assert "manual-isolated" not in local_job
    assert "turso.io" not in local_job
    assert "http://" not in local_job
    assert "https://" not in local_job
    assert "DRAMA_ENABLE_TXLAB" not in local_job
    assert "python -m compileall" in before
    assert "ffprobe" in after


def test_local_sdk_contract_is_explicitly_local_without_remote_connect_strings():
    module = (
        Path(__file__).resolve().parent / "test_libsql_sdk_local_only.py"
    ).read_text()
    assert "pytest.importorskip(\"libsql\")" in module
    assert 'assert "://" not in database' in module
    assert "SCHEMA_V3" in module
    assert "conn.execute(ddl)" in module
    assert "conn.executescript(" not in module
    assert "PRAGMA foreign_keys=ON" in module
    assert "conn.close()" in module
    assert "DRAMA_TURSO_AUTH_TOKEN" not in module
    assert "DRAMA_TXLAB_AUTH_TOKEN" not in module
