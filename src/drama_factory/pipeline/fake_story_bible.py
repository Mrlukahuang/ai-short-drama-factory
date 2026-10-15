"""AMEND-005 P1: reproducible LOCAL synopsis -> Fake Story Bible JSON.

This does not write to Series/Bible tables, approve fiction, use TextProvider
model APIs, infer characters, or claim to have created an authored screenplay.
P2 will use the existing FakeTextProvider AFTER a scoped Bible has been saved.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import tempfile
from pathlib import Path

from drama_factory.models import StoryBible

MAX_BRIEF_BYTES = 16 * 1024
SCHEMA = "fake-story-bible.zh.v1"


class FakeSynopsisError(ValueError):
    pass


def build_fake_story_bible(source: Path) -> dict:
    """Pure local bounded original text -> existing canonical StoryBible."""
    path = Path(source)
    if path.is_symlink() or not path.is_file() or path.suffix.lower() != ".txt":
        raise FakeSynopsisError("Input must be a local regular .txt synopsis, not a symlink")
    try:
        size = path.stat().st_size
        if not 1 <= size <= MAX_BRIEF_BYTES:
            raise FakeSynopsisError("Synopsis must be 1–16384 UTF-8 bytes")
        data = path.read_bytes()
        if len(data) != size:
            raise FakeSynopsisError("Source changed while reading")
        text = data.decode("utf-8", errors="strict")
    except UnicodeError:
        raise FakeSynopsisError("Synopsis must be UTF-8") from None
    if any(ord(c) < 32 and c not in "\n\r\t" for c in text):
        raise FakeSynopsisError("Synopsis contains forbidden control characters")
    lines = [s.strip() for s in text.splitlines() if s.strip()]
    if not lines or len(" ".join(lines)) < 8:
        raise FakeSynopsisError("Original synopsis is too short")
    # These fields are explicitly placeholders; this code performs no story
    # interpretation or character inference, and never claims to be an LLM.
    title = lines[0][:200]
    logline = " ".join(lines)[:1200]
    bible = StoryBible(
        title=title,
        logline=logline,
        genre="未定（Fake 模板）",
        canon="FAKE_ONLY：从本地原创梗概复制摘要；人物、世界规则及版权未经审阅。",
        relationship_notes="FAKE_ONLY：关系、角色与视觉描述留待人工或后续独立步骤确认。",
    )
    return {
        "schema_version": SCHEMA,
        "step": "01_story_bible",
        "source_sha256": hashlib.sha256(data).hexdigest(),
        "source_bytes": len(data),
        "status": "fake_only",
        "fake_only": True,
        "approval_granted": False,
        "ready_for_approval": False,
        "provider": "local_deterministic_template",
        "model_calls": 0,
        "paid_api_calls": 0,
        "actual_fee_usd": None,
        "story_bible": bible.model_dump(mode="json"),
    }


def write_fake_story_bible(result: dict, destination: Path) -> Path:
    """Atomically write one local JSON output; never follow output symlinks."""
    out = Path(destination)
    if out.suffix.lower() != ".json" or out.is_symlink() or out.exists():
        raise FakeSynopsisError("Output must be a new non-linked .json path")
    if not out.parent.is_dir() or out.parent.is_symlink():
        raise FakeSynopsisError("Output parent must be an existing local directory")
    payload = json.dumps(result, ensure_ascii=False, sort_keys=True, indent=2) + "\n"
    temporary = None
    try:
        with tempfile.NamedTemporaryFile(
            mode="w", encoding="utf-8", dir=out.parent,
            prefix=".fake-bible-", suffix=".json", delete=False,
        ) as stream:
            temporary = Path(stream.name)
            stream.write(payload)
            stream.flush()
            os.fsync(stream.fileno())
        # Atomic, non-replacing creation on supported local filesystems.
        os.link(temporary, out)
        return out
    except FileExistsError:
        raise FakeSynopsisError("Output already exists") from None
    finally:
        if temporary is not None:
            temporary.unlink(missing_ok=True)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="P1 Fake Story Bible: no model calls")
    parser.add_argument("synopsis", type=Path, help="local original UTF-8 .txt")
    parser.add_argument("--output", type=Path, required=True, help="new local .json file")
    args = parser.parse_args(argv)
    try:
        result = build_fake_story_bible(args.synopsis)
        write_fake_story_bible(result, args.output)
    except (FakeSynopsisError, OSError) as exc:
        parser.exit(2, f"Fake P1 denied: {exc}\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
