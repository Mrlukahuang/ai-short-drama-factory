"""Owner-authorized first three text attempts. Default: offline plan only.

This isolated CLI is the ONLY new live transport; the pure adapter stays offline.
No automatic retry, continuation, fallback model, video, DB or approval writes.
"""
from __future__ import annotations

import argparse
from dataclasses import asdict
from datetime import datetime
from decimal import Decimal
import json
import os
from pathlib import Path
from urllib.error import HTTPError
from urllib.request import HTTPRedirectHandler, Request, build_opener
from zoneinfo import ZoneInfo

from prepare_writer_comparison import case_inputs
from drama_factory.pipeline.writer_execution_prep import (
    MODELS, RATE_START, RATE_EXPIRY, parse_response, prepare_request,
)

REPO = "Mrlukahuang/ai-short-drama-factory"
CONFIRM = "RUN_WRITER_FIRST3_USD2"
MARKER = "[WRITER_FIRST3_20261018_USD2_ONE_TIME_CLAIM]"
COUNT_URL = "https://api.openai.com/v1/responses/input_tokens"
COMMENTS = f"https://api.github.com/repos/{REPO}/issues/146/comments"
MAX_OUTPUT = 12000
GOOGLE_INPUT_UPPER = 1048576


class NoRedirect(HTTPRedirectHandler):
    def redirect_request(self, *args, **kwargs):
        return None


class SafeTransportError(RuntimeError):
    def __init__(self, status):
        self.http_status = status
        super().__init__(f"HTTP {status}; no automatic retry")


def request_json(url: str, key: str, body: dict | None, *, google=False):
    """Single HTTPS request, no redirects or retries, never print headers/body."""
    headers = {"Content-Type": "application/json", "User-Agent": "drama-writer-pilot"}
    headers.update({"x-goog-api-key": key} if google else {"Authorization": f"Bearer {key}"})
    req = Request(url, data=json.dumps(body).encode() if body is not None else None,
                  headers=headers, method="POST" if body is not None else "GET")
    try:
        with build_opener(NoRedirect()).open(req, timeout=240) as stream:
            raw = stream.read(8 * 1024 * 1024 + 1)
        if len(raw) > 8 * 1024 * 1024:
            raise RuntimeError("Response too large; do not retry")
        return json.loads(raw)
    except HTTPError as exc:
        # Do not expose error bodies that may echo requests or headers.
        raise SafeTransportError(exc.code) from None


def pilot_budget(counts: dict, spend_today: str, on) -> dict:
    """Reserve three attempts, not a release of the entire 18-task batch.

    Exact OpenAI input counts include schema/formatting. Reserve at least 10k
    inputs and 25% headroom for count/rate/cache-write differences. Google uses
    its entire documented model input ceiling, not a local token heuristic.
    Standard global list-price assumptions; no tools or regional endpoints.
    """
    if not RATE_START <= on <= RATE_EXPIRY:
        raise ValueError("Reverify expired pricing snapshot")
    spend = Decimal(spend_today)
    if not spend.is_finite() or spend < 0:
        raise ValueError("Invalid reported daily spend")
    reservations = {}
    for model, rate_in, rate_out in ((MODELS[0], "2", "10"), (MODELS[1], ".10", ".50")):
        count = counts.get(model)
        if type(count) is not int or not 0 < count <= 217600:
            raise ValueError("OpenAI full-request count missing/too large")
        upper = max(10000, (count * 5 + 3) // 4)
        reservations[model] = {
            "input_upper": upper, "output_upper": MAX_OUTPUT,
            "reserved_usd": str((Decimal(upper) * Decimal(rate_in) * Decimal("1.25")
                                  + MAX_OUTPUT * Decimal(rate_out)) / 1000000)}
    reservations[MODELS[2]] = {
        "input_upper": GOOGLE_INPUT_UPPER, "output_upper": MAX_OUTPUT,
        "reserved_usd": str((Decimal(GOOGLE_INPUT_UPPER) * Decimal(".75")
                              + MAX_OUTPUT * Decimal("3.75")) / 1000000)}
    total = sum((Decimal(r["reserved_usd"]) for r in reservations.values()), Decimal(0))
    if total > 2 or spend + total > 5:
        raise ValueError("Pilot exceeds USD2 total or USD5 daily envelope")
    return {"reserved_usd": str(total), "reservations": reservations,
            "actual_invoice_verified": False, "remaining_15_authorized_by_this_runner": False}


def claim_once(token: str, run_id: str, post=request_json) -> None:
    # Workflow serial concurrency protects read-then-claim; paginate to avoid
    # missing the persistent marker. A consumed claim is never auto-released.
    for page in range(1, 11):
        comments = post(f"{COMMENTS}?per_page=100&page={page}", token, None)
        if not isinstance(comments, list):
            raise RuntimeError("Invalid claim history")
        if any(MARKER in str(c.get("body", "")) for c in comments):
            raise RuntimeError("Pilot already claimed; no repeat charges")
        if len(comments) < 100:
            break
    else:
        raise RuntimeError("Claim history too long; fail closed")
    receipt = post(COMMENTS, token, {"body": f"{MARKER}\n"
        f"Owner-authorized first3, USD2 total / USD5 daily. Run {run_id}: "
        f"https://github.com/{REPO}/actions/runs/{run_id}\n"
        "Claim precedes generation, not proof of charges. No reruns after ambiguity."})
    if type(receipt.get("id")) is not int:
        raise RuntimeError("Claim not acknowledged; do not generate")


def write_json(path: Path, value: dict):
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    path.chmod(0o600)


def run_live(out: Path, spend_today: str, *, env, post=request_json) -> dict:
    if (env.get("GITHUB_REPOSITORY") != REPO or env.get("GITHUB_EVENT_NAME") != "workflow_dispatch"
            or env.get("GITHUB_REF") != "refs/heads/main"
            or env.get("GITHUB_RUN_ATTEMPT") != "1" or env.get("GITHUB_ACTOR") != "Mrlukahuang"
            or env.get("WRITER_PILOT_CONFIRM") != CONFIRM):
        raise RuntimeError("Explicit owner first-attempt manual Actions context required")
    keys = {"openai": env.get("OPENAI_API_KEY"), "google": env.get("GEMINI_API_KEY"),
            "github": env.get("GITHUB_TOKEN")}
    if not all(keys.values()):
        raise RuntimeError("Required secret absent (values are never printed)")
    out.mkdir(parents=True, exist_ok=False)
    report = {"status": "preflight", "generation_attempts": 0, "results": [],
              "actual_invoice_verified": False, "paid_reservation_claimed": False,
              "reported_spend_today_usd": spend_today, "run_id": env["GITHUB_RUN_ID"],
              "source_sha": env.get("GITHUB_SHA"),
              "authorization": "owner first3 within 18, USD2 total, no automatic retries"}
    prepared = [prepare_request(m, *case_inputs("misunderstanding")) for m in MODELS]
    on = datetime.now(ZoneInfo("Pacific/Auckland")).date()
    try:
        counts = {}
        for req in prepared[:2]:
            body = json.loads(req.payload_json)
            counted = post(COUNT_URL, keys["openai"], body)
            if counted.get("object") != "response.input_tokens":
                raise RuntimeError("Unrecognized OpenAI token count receipt")
            counts[req.model] = counted.get("input_tokens")
        report["budget"] = pilot_budget(counts, spend_today, on)
        report["openai_full_request_counts"] = counts
        write_json(out / "report.json", report)
        claim_once(keys["github"], env["GITHUB_RUN_ID"], post)
        report["paid_reservation_claimed"] = True
        for req in prepared:
            report["generation_attempts"] += 1
            report["status"] = "request_in_flight"
            write_json(out / "report.json", report)  # Preserve uncertain timeout attempt.
            response = post(req.endpoint, keys["google"] if req.model.startswith("gemini-")
                            else keys["openai"], json.loads(req.payload_json),
                            google=req.model.startswith("gemini-"))
            write_json(out / f"{req.model}.response.json", response)
            parsed = parse_response(req, response, on=on, simulated=False)
            usage = asdict(parsed.usage) if parsed.usage else None
            report["results"].append({"model": req.model, "job_id": f"misunderstanding/{req.model}/1",
                "status": parsed.status, "usage": usage, "usage_status": parsed.usage_status,
                "request_sha256": parsed.request_sha256, "response_sha256": parsed.response_sha256,
                "response_id": parsed.response_id, "approval_granted": False})
            if parsed.screenplay:
                write_json(out / f"{req.model}.screenplay.json", parsed.screenplay.model_dump(mode="json"))
            bound = report["budget"]["reservations"][req.model]
            if (not parsed.usage or parsed.usage.input_tokens > bound["input_upper"]
                    or parsed.usage.billable_output_tokens > MAX_OUTPUT
                    or Decimal(parsed.usage.estimated_usd) > Decimal(bound["reserved_usd"])
                    or parsed.status != "validated_draft"):
                raise RuntimeError("Pilot failed validation/usage/bounds; stop without retry")
        report["status"] = "first3_completed_pending_human_review"
    except Exception as exc:
        report["status"] = "halted_no_retry"
        report["error_category"] = type(exc).__name__
        if isinstance(exc, SafeTransportError):
            report["http_status"] = exc.http_status
        # Never print exception messages from network libraries or provider JSON.
        raise RuntimeError("Pilot halted; inspect private report/artifact, do not rerun") from None
    finally:
        write_json(out / "report.json", report)
    return report


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--paid", action="store_true")
    parser.add_argument("--reported-spend-today-usd")
    parser.add_argument("--out", type=Path, default=Path("artifacts/writer-first3"))
    args = parser.parse_args(argv)
    if not args.paid:
        print(json.dumps({"status": "offline_plan_only", "models": MODELS,
                          "generation_attempts": 0, "limit_usd": "2", "max_output_tokens": MAX_OUTPUT}))
        return 0
    if args.reported_spend_today_usd is None:
        parser.error("Verified reported daily spend required")
    run_live(args.out, args.reported_spend_today_usd, env=os.environ)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
