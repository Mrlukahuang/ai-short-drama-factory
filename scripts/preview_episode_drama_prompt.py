"""G4 R4.2: offline preview of one versioned Chinese drama-writing prompt.

This command never creates an episode, calls a provider, approves a draft,
or modifies any database. Input/source may be private: outputs are local only.
"""
from __future__ import annotations

import argparse
import json
import os
from pathlib import Path

from drama_factory.pipeline.text import (
    DRAMA_PROMPT_VERSION,
    ScriptContext,
    ScriptPlanRequest,
    build_drama_writer_prompt,
)


def _load_json(path: Path) -> dict:
    if path.is_symlink() or not path.is_file() or path.stat().st_size > 65536:
        raise ValueError("Input must be a regular local JSON document <=64 KiB")
    doc = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(doc, dict):
        raise ValueError("Input must be one JSON object")
    return doc


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description="Preview offline G4 R4.2 writing prompt")
    p.add_argument("--request-json", type=Path, required=True)
    p.add_argument("--context-json", type=Path, required=True)
    p.add_argument("--out", type=Path, required=True)
    args = p.parse_args(argv)
    request = ScriptPlanRequest.model_validate(_load_json(args.request_json))
    context = ScriptContext.model_validate(_load_json(args.context_json))
    if request.prompt_version != DRAMA_PROMPT_VERSION:
        p.error("Explicit prompt_version episode-drama-beats.zh.v1 required")
    doc = build_drama_writer_prompt(request, context)
    doc.update({
        "model_calls": 0, "paid_api_calls": 0, "approval_granted": False,
        "publish_approved": False, "output_is_prompt_only": True,
    })
    out = args.out
    if out.is_symlink() or not out.parent.is_dir():
        raise ValueError("Output must be a new file in an existing local directory")
    # Atomic create-only, no overwrite, mode 0600 for a private script brief.
    fd = os.open(out, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    with os.fdopen(fd, "w", encoding="utf-8") as stream:
        json.dump(doc, stream, ensure_ascii=False, sort_keys=True, indent=2)
        stream.write("\n")
    print(json.dumps({
        "prompt_version": doc["prompt_version"],
        "prompt_sha256": doc["prompt_sha256"],
        "output_is_prompt_only": True, "model_calls": 0,
    }, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
