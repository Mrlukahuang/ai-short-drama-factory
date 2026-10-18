#!/usr/bin/env python3
"""G4/R4.3 W4: run read-only QA against W3 original and W1-FAKE artifacts.

Requires locally downloaded W3 files. Does not download media or call models.
"""
import argparse
import json
import os
import sys
from pathlib import Path

from drama_factory.pipeline.content_review import (
    ContentReviewError, assess_bundle, load_w3_bundle,
)


def _read_reviews(path):
    if path is None:
        return {"original": [], "w1_fake": []}
    if path.is_symlink() or path.stat().st_size > 128 * 1024:
        raise ContentReviewError("Unsafe review import")
    data = json.loads(path.read_text("utf-8"))
    if type(data) is not dict or set(data) != {"original", "w1_fake"}:
        raise ContentReviewError("Expected exact original/w1_fake review lists")
    return data


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--original-dir", type=Path, required=True)
    parser.add_argument("--fake-dir", type=Path, required=True)
    parser.add_argument("--original-sha", required=True)
    parser.add_argument("--fake-sha", required=True)
    parser.add_argument("--original-artifact-id", type=int, required=True)
    parser.add_argument("--fake-artifact-id", type=int, required=True)
    parser.add_argument("--reviews-json", type=Path, help="Optional signed human reviews, local only")
    parser.add_argument("--reviewer", help="Explicit trusted reviewer ID; requires credential file")
    parser.add_argument("--reviewer-key-file", type=Path, help="Private 32+ byte credential, never commit")
    parser.add_argument("--output-dir", type=Path, required=True)
    args = parser.parse_args(argv)
    if bool(args.reviewer) != bool(args.reviewer_key_file):
        parser.error("reviewer and reviewer-key-file must be supplied together")
    keys = {}
    if args.reviewer:
        credential = args.reviewer_key_file
        if credential.is_symlink() or not credential.is_file():
            parser.error("Unsafe credential path")
        if os.name == "posix" and credential.stat().st_mode & 0o077:
            parser.error("Credential file must not be readable by group/others")
        raw_key = credential.read_bytes()
        if len(raw_key) < 32 or len(raw_key) > 4096:
            parser.error("Credential must contain 32..4096 raw bytes")
        keys = {args.reviewer: raw_key}
    try:
        original = load_w3_bundle(args.original_dir, artifact_id=args.original_artifact_id,
                                  version="original", expected_mp4_sha256=args.original_sha)
        fake = load_w3_bundle(args.fake_dir, artifact_id=args.fake_artifact_id,
                              version="w1_fake", expected_mp4_sha256=args.fake_sha, parent=original)
        reviews = _read_reviews(args.reviews_json)
        outputs = {
            "original": assess_bundle(original, reviews["original"], reviewer_keys=keys),
            "w1_fake": assess_bundle(fake, reviews["w1_fake"], reviewer_keys=keys),
        }
        if args.output_dir.exists():
            raise ContentReviewError("Output must be a fresh, unmodified directory")
        if any(args.output_dir.resolve().is_relative_to(x.resolve())
               for x in (args.original_dir, args.fake_dir)):
            raise ContentReviewError("Output must not overwrite source media")
        args.output_dir.mkdir(parents=True, exist_ok=False)
        for version, report in outputs.items():
            (args.output_dir / (version + "-content-qa.json")).write_text(
                json.dumps(report, indent=2, ensure_ascii=False, sort_keys=True) + "\n",
                encoding="utf-8",
            )
        print(json.dumps({
            version: {"report_sha256": report["report_sha256"],
                      "content_qa": report["content_qa"],
                      "technical_qa": report["technical_qa"],
                      "release_qa": report["release_qa"],
                      "usable": report["usable_shot_count"],
                      "human_review_attested": report["human_review_attested_count"]}
            for version, report in outputs.items()
        }, sort_keys=True))
    except (ContentReviewError, KeyError, OSError, ValueError) as exc:
        print("W4 offline QA rejected invalid or incomplete evidence: "
              + type(exc).__name__, file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
