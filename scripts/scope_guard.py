#!/usr/bin/env python3
"""Anti-drift scope guard (AMEND-001 / docs/GUARDRAILS.md).

Fails a pull request when it:
  1. touches frozen paths without the owner-applied ``amend-approved`` label,
  2. touches governance files (AMEND/AGENTS/GUARDRAILS/STAGES/guard itself)
     without that label, or
  3. lacks ``Stage: Gx`` and ``Req: Rx.y`` lines in the PR description.

Usage (CI):
    python scripts/scope_guard.py --base origin/main
Environment:
    PR_BODY    pull request description (empty -> body check skipped, e.g. push to main)
    PR_LABELS  comma-separated label names
"""
from __future__ import annotations

import argparse
import fnmatch
import os
import re
import subprocess
import sys

# Keep in sync with AMEND.md -> AMEND-001.
FROZEN_GLOBS: tuple[str, ...] = (
    "src/drama_factory/storage/txlab_*",
    "src/drama_factory/storage/pr31_*",
    "src/drama_factory/storage/libsql_*",
    "src/drama_factory/storage/turso_*",
    "src/drama_factory/storage/cutover_*",
    "src/drama_factory/storage/migration_readiness.py",
    "src/drama_factory/storage/snapshot_rehearsal.py",
    "src/drama_factory/jobs/tts_*",
    ".github/workflows/*txlab*",
    ".github/workflows/*turso*",
    ".github/workflows/*drive*",
    ".github/workflows/*cloud-canary*",
    "docs/PR31_*",
    "docs/TURSO_*",
)

# Governance files: agents may self-merge green PRs (AMEND-004) but never these.
GOVERNANCE_FILES: tuple[str, ...] = (
    "AMEND.md",
    "AGENTS.md",
    "CLAUDE.md",
    "docs/GUARDRAILS.md",
    "docs/STAGES.md",
    "scripts/scope_guard.py",
    ".github/workflows/scope-guard.yml",
)

OVERRIDE_LABEL = "amend-approved"
STAGE_RE = re.compile(r"^\s*Stage:\s*G\d+\b", re.MULTILINE)
REQ_RE = re.compile(r"^\s*Req:\s*R\d+(\.\d+)?\b", re.MULTILINE)


def frozen_hits(paths: list[str]) -> list[str]:
    return [p for p in paths if any(fnmatch.fnmatch(p, g) for g in FROZEN_GLOBS)]


def governance_hits(paths: list[str]) -> list[str]:
    return [p for p in paths if p in GOVERNANCE_FILES]


def body_problems(body: str) -> list[str]:
    problems = []
    if not STAGE_RE.search(body):
        problems.append("PR 描述缺少 `Stage: Gx`（见 docs/STAGES.md）")
    if not REQ_RE.search(body):
        problems.append("PR 描述缺少 `Req: Rx.y`（见 docs/STAGES.md）")
    return problems


def check(paths: list[str], body: str, labels: set[str]) -> list[str]:
    errors: list[str] = []
    hits = frozen_hits(paths)
    if hits and OVERRIDE_LABEL not in labels:
        errors.append(
            "修改了 AMEND-001 冻结路径（需所有者加 `amend-approved` 标签）：\n  - "
            + "\n  - ".join(hits)
        )
    gov = governance_hits(paths)
    if gov and OVERRIDE_LABEL not in labels:
        errors.append(
            "修改了治理文件，只有所有者可批准（需 `amend-approved` 标签）：\n  - "
            + "\n  - ".join(gov)
        )
    if body.strip():
        errors.extend(body_problems(body))
    return errors


def changed_files(base: str) -> list[str]:
    out = subprocess.run(
        ["git", "diff", "--name-only", f"{base}...HEAD"],
        check=True, capture_output=True, text=True,
    ).stdout
    return [line for line in out.splitlines() if line]


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--base", default="origin/main")
    args = parser.parse_args()
    labels = {x.strip() for x in os.environ.get("PR_LABELS", "").split(",") if x.strip()}
    errors = check(changed_files(args.base), os.environ.get("PR_BODY", ""), labels)
    if errors:
        print("❌ Scope guard 未通过（docs/GUARDRAILS.md）：")
        for e in errors:
            print(f"- {e}")
        return 1
    print("✅ Scope guard 通过")
    return 0


if __name__ == "__main__":
    sys.exit(main())
