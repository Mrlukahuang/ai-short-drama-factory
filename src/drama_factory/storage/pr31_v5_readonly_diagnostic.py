"""One-use TxLab v5 READ-ONLY postmortem: never retries v5 writer.

Every SQL statement below is a fixed SELECT or read-oriented PRAGMA/BEGIN.
The exact dataset is the existing, already-written synthetic pr31_v5_*
prefix. Never connects to production or exposes SQL errors/identifiers.
"""
from __future__ import annotations

import argparse
import json
import os
import sys

from drama_factory.storage.libsql_txlab import validate_lab_url, _open_lab_connection, _close_quietly


class V5ReadOnlyDenied(ValueError):
    pass


def inspect_v5_existing_readonly(factory) -> dict:
    """Independent bounded probes, each with a fresh database connection.

    Query-only PRAGMA compatibility is assessed separately from plain SQL
    snapshots: no chance of modifying the ledger through this module.
    """
    stages = {}
    observed = {}
    tasks = (
        ("select_one", "SELECT 1", (1,)),
        ("query_only_pragma", "PRAGMA query_only=ON", None),
        ("gate", "SELECT epoch,state FROM pr31_v5_gate WHERE id=1", (2, "paused")),
        ("readiness", "SELECT COUNT(*) FROM pr31_v5_ready", (2,)),
        ("holds", "SELECT COUNT(*) FROM pr31_v5_holds", (1,)),
        ("intent_audit", "SELECT COUNT(*) FROM pr31_v5_events WHERE action='generation_intent_recorded'", (1,)),
        ("fence_audit", "SELECT COUNT(*) FROM pr31_v5_events WHERE action='fenced_hold_and_intent'", (1,)),
        ("pause_audit", "SELECT COUNT(*) FROM pr31_v5_events WHERE action='pause'", (1,)),
        ("foreign_key_check", "PRAGMA foreign_key_check", ()),
    )
    for name, sql, expected in tasks:
        c = None
        try:
            c = factory()
            cursor = c.execute(sql)
            if name == "foreign_key_check":
                result = cursor.fetchall()
                stages[name] = "ok" if not result else "integrity_mismatch"
            elif name == "query_only_pragma":
                stages[name] = "ok"
            else:
                result = cursor.fetchone()
                stages[name] = "ok" if result is not None and tuple(result) == expected else "unexpected_readback"
        except Exception:
            stages[name] = "query_unavailable"
        finally:
            _close_quietly(c)
    # A read snapshot is a *new* connection, not a rerun of failed observer
    # or any previously attempted remote COMMIT.
    c = None
    try:
        c = factory()
        c.execute("BEGIN")
        row = c.execute(
            "SELECT (SELECT COUNT(*) FROM pr31_v5_holds), "
            "(SELECT COUNT(*) FROM pr31_v5_ready), "
            "(SELECT COUNT(*) FROM pr31_v5_events)"
        ).fetchone()
        stages["read_snapshot"] = "ok" if row and tuple(row) == (1, 2, 3) else "unexpected_readback"
    except Exception:
        stages["read_snapshot"] = "query_unavailable"
    finally:
        _close_quietly(c)

    # A priori status: even a completely consistent read cannot certify
    # network COMMIT ambiguity, server clock, production safety or billing.
    return {
        "mode": "isolated_turso_v5_select_only_postmortem",
        "stages": stages,
        "ledger_probes_consistent": all(
            stages[x] == "ok" for x in (
                "select_one", "gate", "readiness", "holds", "intent_audit",
                "fence_audit", "pause_audit", "foreign_key_check", "read_snapshot",
            )
        ),
        "prior_query_only_pragma_compatible": stages["query_only_pragma"] == "ok",
        "additional_remote_writes": 0,
        "paid_provider_calls": 0,
        "production_database_touched": False,
        "remote_multi_runner_verified": False,
        "network_commit_ack_loss_verified": False,
        "may_retry_original_v5_run": False,
        "live_cutover_permitted": False,
    }


def cli(argv=None) -> int:
    parser = argparse.ArgumentParser(description="READ-ONLY v5 independently scoped postmortem")
    parser.parse_args(argv)
    if (
        os.getenv("DRAMA_V5_READONLY_CONFIRM") != "RUN_V5_SELECT_ONLY_DIAG_ONCE"
        or os.getenv("DRAMA_V5_DIAG_MAX_USD") != "2.00"
        or os.getenv("GITHUB_REF") != "refs/heads/main"
        or os.getenv("GITHUB_RUN_ATTEMPT") != "1"
    ):
        print("v5 readonly inspection denied: strict one-run gate missing", file=sys.stderr)
        return 1
    try:
        url = validate_lab_url(os.environ.get("DRAMA_TXLAB_DATABASE_URL", ""))
        token = os.environ.get("DRAMA_TXLAB_AUTH_TOKEN", "")
        if not token:
            raise V5ReadOnlyDenied("Dedicated isolated read token required")
        report = inspect_v5_existing_readonly(lambda: _open_lab_connection(url, token))
        print(json.dumps(report, sort_keys=True))
        return 0
    except Exception:
        print("v5 READ-ONLY diagnostic unavailable (redacted), never rerun writer", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(cli())
