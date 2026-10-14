"""PR-10o: offline-only, immutable original Google context assertion.

This is an unverified *local* provenance label: it is NOT authentication,
credential validation, a live Google adapter, or permission to dispatch/get.
Never persist API keys, raw account/project IDs, subject names or request text.
"""
from __future__ import annotations

import re

from drama_factory.db import Database, timestamp


class TtsGoogleOriginDenied(ValueError):
    """Error strings must not disclose project, principal or TTS identifiers."""


def _valid_digest(value: str) -> bool:
    return type(value) is str and re.fullmatch(r"[0-9a-f]{64}", value) is not None


def bind_offline_tts_google_origin(
    db: Database, task_id: str, *,
    project_ref_sha256: str,
    principal_ref_sha256: str,
) -> dict:
    """Bind immutable, explicitly UNVERIFIED original origin before paid intent.

    These values are opaque digest labels of approved *nonsecret* project and
    credential-principal references supplied by the operator's local fixture.
    They must never be computed from actual API keys or raw tokens.
    """
    if type(task_id) is not str or not re.fullmatch(r"ttstask_[a-f0-9]{14}", task_id):
        raise TtsGoogleOriginDenied("Invalid opaque TTS task ID")
    if (
        not _valid_digest(project_ref_sha256)
        or not _valid_digest(principal_ref_sha256)
        or project_ref_sha256 == principal_ref_sha256
    ):
        raise TtsGoogleOriginDenied("Opaque Google context digests required")
    with db.connection() as conn:
        conn.execute("BEGIN IMMEDIATE")
        task = conn.execute(
            "SELECT status,provider FROM tts_tasks WHERE id=?", (task_id,),
        ).fetchone()
        if task is None or task["provider"] != "google" or task["status"] != "prepared":
            raise TtsGoogleOriginDenied("Only unsubmitted Google TTS task may bind origin")
        existing = conn.execute(
            """SELECT project_ref_sha256,principal_ref_sha256
               FROM tts_google_origin_scopes WHERE task_id=?""", (task_id,),
        ).fetchone()
        if existing is not None:
            if (
                existing["project_ref_sha256"] != project_ref_sha256
                or existing["principal_ref_sha256"] != principal_ref_sha256
            ):
                raise TtsGoogleOriginDenied("Existing original Google scope cannot change")
        else:
            conn.execute(
                """INSERT INTO tts_google_origin_scopes
                   (task_id,project_ref_sha256,principal_ref_sha256,source,created_at)
                   VALUES (?,?,?,'offline_unverified',?)""",
                (task_id, project_ref_sha256, principal_ref_sha256, timestamp()),
            )
    return {
        "kind": "offline_google_origin_scope_bound",
        "immutable_original_scope_recorded": True,
        "scope_authentication_verified": False,
        "provider_permissions_verified": False,
        "new_google_requests": 0,
        "live_readback_allowed": False,
        "paid_dispatch_allowed": False,
        "production_cutover_allowed": False,
    }
