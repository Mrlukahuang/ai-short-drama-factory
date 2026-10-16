"""Reserve the single owner-authorized paid F3 run on Issue #137.

Requires the GitHub Actions GITHUB_TOKEN, issues:write, and the workflow's
serial concurrency group. Refuse any later attempt after a reservation, even
if the first job failed halfway through video generation. Never prints token.
"""
from __future__ import annotations

import json
import os
from urllib.request import Request, urlopen

MARKER = "[F3_ISSUE_137_ONE_TIME_PAID_RUN_CLAIM]"
REPO = "Mrlukahuang/ai-short-drama-factory"
URL = f"https://api.github.com/repos/{REPO}/issues/137/comments?per_page=100"


def has_prior_claim(comments: list[dict]) -> bool:
    if not isinstance(comments, list):
        raise ValueError("Invalid Issue comments response")
    return any(MARKER in str(c.get("body") or "") for c in comments)


def claim_one_run(*, token: str, run_id: str, run_attempt: str = "1") -> int:
    if not token or not run_id or not run_id.isdecimal() or run_attempt != "1":
        raise ValueError("One-time F3 GitHub owner run context required")
    headers = {
        "Authorization": f"Bearer {token}",
        "Accept": "application/vnd.github+json",
        "X-GitHub-Api-Version": "2022-11-28",
        "User-Agent": "f3-once-budget-issue-137",
    }
    req = Request(URL, headers=headers)
    with urlopen(req, timeout=20) as response:
        comments = json.load(response)
    # Fail closed rather than miss a marker on another page.
    if len(comments) >= 100:
        raise RuntimeError("Issue comments require pagination; F3 charge denied")
    if has_prior_claim(comments):
        raise RuntimeError("Issue #137 already reserved: do NOT submit another paid run")
    comment = {
        "body": (
            f"{MARKER}\n"
            f"Run ID: {run_id}; [Actions run](https://github.com/{REPO}/actions/runs/{run_id})\n"
            "Owner one-time approval: USD2.50/run, USD5/day; 360p six-shot F3.\n"
            "Reservation BEFORE any paid request; this does not prove a model call "
            "or charge happened. No automatic retries, even after failure."
        )
    }
    req = Request(
        URL, data=json.dumps(comment).encode("utf-8"),
        headers={**headers, "Content-Type": "application/json"}, method="POST",
    )
    with urlopen(req, timeout=20) as response:
        result = json.load(response)
    if not isinstance(result.get("id"), int):
        raise RuntimeError("Issue claim not acknowledged: no paid requests permitted")
    return result["id"]


def main() -> None:
    if os.getenv("GITHUB_REPOSITORY") != REPO:
        raise RuntimeError("Wrong repository: no paid F3 request")
    result = claim_one_run(
        token=os.getenv("GITHUB_TOKEN", ""),
        run_id=os.getenv("GITHUB_RUN_ID", ""),
        run_attempt=os.getenv("GITHUB_RUN_ATTEMPT", ""),
    )
    print(f"F3 one-time reservation confirmed on Issue #137: comment {result}")


if __name__ == "__main__":
    main()
