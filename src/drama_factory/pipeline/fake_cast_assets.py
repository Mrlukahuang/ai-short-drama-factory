"""AMEND-005 P3: bind P2 provisional cast/scene IDs to LOCAL Fake DB assets.

No schema migration, user photos, voice cloning, Provider call, approval or
production run. Creates deterministic Fake-only rows in existing SQLite
Series/StoryBible/series_assets, exclusively for offline pipeline rehearsal.
"""
from __future__ import annotations

import hashlib
import json
import sqlite3

from drama_factory.db import Database, DEFAULT_COLUMN_ID, timestamp
from drama_factory.models import ActorBible, SceneBible, StoryBible, VoiceBible
from drama_factory.pipeline.fake_episode_screenplay import (
    SCRIPT_STAGE_SCHEMA, build_fake_episode_screenplay,
)
from drama_factory.pipeline.screenplay import Screenplay, check_screenplay_scope


class FakeAssetBindingError(ValueError):
    pass


def _id(seed: str) -> str:
    return "asset_" + hashlib.sha256(seed.encode("utf-8")).hexdigest()[:14]


def _existing_or_insert(conn, *, table: str, key: str, values: dict) -> None:
    """Idempotent immutable inserts; reject any pre-existing conflicting row."""
    if table not in {"projects", "story_bibles", "series_assets"}:
        raise FakeAssetBindingError("Unexpected local Fake asset table")
    record = conn.execute(
        f"SELECT * FROM {table} WHERE id=?", (key,),
    ).fetchone()
    if record is None:
        cols = list(values)
        conn.execute(
            f"INSERT INTO {table} ({','.join(cols)}) "
            f"VALUES ({','.join('?' for _ in cols)})",
            tuple(values[x] for x in cols),
        )
        return
    for field, expected in values.items():
        if field == "created_at":
            continue
        if record[field] != expected:
            raise FakeAssetBindingError("Conflicting existing Fake asset ID or version")


def bind_fake_cast_assets(db: Database, bible_payload: dict, episode_payload: dict) -> dict:
    """Make each P2 reference DB-backed, yet keep ALL approvals as false.

    All-or-none existing-schema SQLite transaction; no new tables. The
    returned manifest is intentionally NOT a commercial/consent certificate.
    """
    if not isinstance(episode_payload, dict) or episode_payload.get("schema_version") != SCRIPT_STAGE_SCHEMA:
        raise FakeAssetBindingError("P2 Fake screenplay required")
    try:
        supplied = Screenplay.model_validate(episode_payload["screenplay"])
        canonical = build_fake_episode_screenplay(
            bible_payload,
            episode_number=supplied.episode_number,
            target_duration_seconds=supplied.target_duration_seconds,
        )
        if episode_payload != canonical:
            raise FakeAssetBindingError("P2 input or provisional reference was altered")
        bible = StoryBible.model_validate(bible_payload["story_bible"])
    except (KeyError, ValueError, TypeError):
        raise FakeAssetBindingError("P1/P2 Fake stage provenance is invalid") from None
    ids = canonical["provisional_refs"]
    sid, bid = supplied.series_id, supplied.story_bible_id
    source = canonical["source_sha256"]
    voice_a, voice_b = _id(source + ":voice-a"), _id(source + ":voice-b")
    specs = [
        (voice_a, "voice", "fake_voice_a", VoiceBible(
            name="FAKE 角色A声音", voice_description="FAKE 合成节奏提示音，非真人语音",
        )),
        (voice_b, "voice", "fake_voice_b", VoiceBible(
            name="FAKE 角色B声音", voice_description="FAKE 合成节奏提示音，非真人语音",
        )),
        (ids["actor_a"], "actor", "fake_actor_a", ActorBible(
            name="FAKE 角色A", appearance="未生成任何演员照片",
            identity_anchors=["FAKE 合成头像引用占位"],
            voice_asset_id=voice_a,
        )),
        (ids["actor_b"], "actor", "fake_actor_b", ActorBible(
            name="FAKE 角色B", appearance="未生成任何演员照片",
            identity_anchors=["FAKE 合成头像引用占位"],
            voice_asset_id=voice_b,
        )),
        (ids["scene"], "scene", "fake_scene", SceneBible(
            name="FAKE 虚构场景", location="纯占位设置",
            layout="未生成实景或真实场景图",
            continuity_notes="FAKE 状态连续性仅供离线分镜测试",
        )),
    ]
    t = timestamp()
    try:
        with db.connection() as conn:
            conn.execute("BEGIN IMMEDIATE")
            _existing_or_insert(conn, table="projects", key=sid, values={
                "id": sid,
                "title": "[FAKE] " + bible.title[:180],
                "premise": bible.logline,
                "visual_style": "live_action",
                "ratio": "9:16",
                "created_at": t,
                "column_id": DEFAULT_COLUMN_ID,
            })
            _existing_or_insert(conn, table="story_bibles", key=bid, values={
                "id": bid, "series_id": sid, "version": 1,
                "body_json": bible.model_dump_json(), "created_at": t,
            })
            result_refs = []
            for asset_id, kind, asset_key, specification in specs:
                body = db.to_json(specification.model_dump(mode="json"))
                _existing_or_insert(conn, table="series_assets", key=asset_id, values={
                    "id": asset_id, "series_id": sid, "kind": kind,
                    "asset_key": asset_key, "version": 1,
                    "specification_json": body, "created_at": t,
                })
                result_refs.append({
                    "asset_id": asset_id, "kind": kind, "key": asset_key,
                    "version": 1,
                    "specification_sha256": hashlib.sha256(
                        body.encode("utf-8")
                    ).hexdigest(),
                    "source_kind": "synthetic_fake_asset",
                    "approved_for_real_model": False,
                })
    except sqlite3.IntegrityError:
        raise FakeAssetBindingError("Fake asset conflicts with existing DB constraints") from None
    # Existing scope validator runs after the transaction; the manifest does
    # not flip any operator approval bits and creates zero Episode/Production.
    check_screenplay_scope(db, supplied)
    return {
        "schema_version": "fake-scoped-assets.zh.v1",
        "step": "04_assets",
        "series_id": sid,
        "story_bible_id": bid,
        "source_sha256": source,
        "fake_only": True,
        "database_scope_verified": True,
        "approval_granted": False,
        "publish_approved": False,
        "paid_api_calls": 0,
        "actual_fee_usd": None,
        "voice_refs": {"actor_a": voice_a, "actor_b": voice_b},
        "assets": result_refs,
        "screenplay": supplied.model_dump(mode="json"),
    }
