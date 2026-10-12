"""Deterministic bounded novel chunk manifests. Never upload source text to a model."""
from __future__ import annotations

import hashlib
from pathlib import Path

CHUNK_SIZE_CHARS = 4000


class SourceIndexError(ValueError):
    pass


def plan_chunks(source_id: str, text: str, chapters: list[dict]) -> list[dict]:
    """Create exact, gap-free offsets inside each already indexed chapter."""
    planned: list[dict] = []
    for chapter in chapters:
        start = chapter["start_offset"]
        end = chapter["end_offset"]
        if not (0 <= start < end <= len(text)):
            raise SourceIndexError("Chapter index is outside extracted text")
        cursor = start
        while cursor < end:
            stop = min(cursor + CHUNK_SIZE_CHARS, end)
            value = text[cursor:stop]
            digest = hashlib.sha256(value.encode("utf-8")).hexdigest()
            token = f"{source_id}:{chapter['ordinal']}:{cursor}:{stop}:{digest}"
            chunk_id = "chunk_" + hashlib.sha256(token.encode("utf-8")).hexdigest()[:28]
            planned.append({
                "id": chunk_id,
                "source_id": source_id,
                "chapter_ordinal": chapter["ordinal"],
                "start_offset": cursor,
                "end_offset": stop,
                "content_sha256": digest,
                "status": "pending",
            })
            cursor = stop
    return planned


def verify_chunks(text: str, planned: list[dict]) -> None:
    """Defence against missing/overlapping slices in the deterministic plan."""
    for prev, current in zip(planned, planned[1:]):
        if prev["chapter_ordinal"] == current["chapter_ordinal"]:
            if prev["end_offset"] != current["start_offset"]:
                raise SourceIndexError("Chunk sequence contains a gap or overlap")
    for part in planned:
        value = text[part["start_offset"]:part["end_offset"]]
        if hashlib.sha256(value.encode("utf-8")).hexdigest() != part["content_sha256"]:
            raise SourceIndexError("Chunk hash mismatch")


def read_extracted_text(data_dir: Path, source_id: str) -> str:
    file_path = data_dir / "novels" / f"{source_id}.txt"
    if not file_path.is_file():
        raise SourceIndexError("Extracted novel text is missing")
    return file_path.read_text(encoding="utf-8")
