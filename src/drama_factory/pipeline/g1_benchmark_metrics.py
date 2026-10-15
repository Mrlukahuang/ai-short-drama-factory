"""G1/R1.6 offline scoring bridge; NO provider requests or real media fixtures.

Scores Chinese transcripts by character error rate when independently supplied,
and probes a supplied LOCAL video using ffprobe. Default planned benchmark
output explicitly has no evidence and all scores are null.
"""
from __future__ import annotations

import json
import math
import re
import subprocess
import unicodedata
from pathlib import Path

from drama_factory.pipeline.media_ingest import MediaIngressError, inspect_source

TRANSCRIBER_MODEL = "gemini-3.5-transcribe"
EXPECTED_MODELS = (
    "gemini-omni-1.1-flash",
    "doubao-seedance-2-5-260628",
    "kling-v3-omni",
)
EXPECTED_SHOTS = ("G1-S1", "G1-S2", "G1-S3")


class G1MetricError(ValueError):
    pass


def _characters(text: str) -> list[str]:
    """Character-level Chinese metric: ignore whitespace/punctuation only."""
    if type(text) is not str or len(text) > 50_000:
        raise G1MetricError("Invalid Chinese dialogue text")
    return [
        c.casefold() for c in unicodedata.normalize("NFKC", text)
        if not c.isspace() and not unicodedata.category(c).startswith("P")
    ]


def character_error_rate(expected: str, heard: str) -> float:
    """Levenshtein substitutions+deletions+insertions / expected char count.

    May exceed 1 for insertions. Empty expected dialogue is NOT scored; the
    silent G1-S3 shot must not be conflated with 100% transcription accuracy.
    """
    a, b = _characters(expected), _characters(heard)
    if not a:
        raise G1MetricError("Cannot compute dialogue accuracy for a silent shot")
    costs = list(range(len(b) + 1))
    for i, char in enumerate(a, 1):
        nxt = [i]
        for j, target in enumerate(b, 1):
            nxt.append(min(nxt[-1] + 1, costs[j] + 1,
                           costs[j - 1] + (char != target)))
        costs = nxt
    return round(costs[-1] / len(a), 6)


def _shot_dialogue(prompt: str) -> str:
    """G1 fixed-shot prompt uses Chinese corner quotes around spoken lines."""
    spoken = re.findall(r"「([^」]*)」", prompt)
    return "".join(spoken)


def _fixed_tasks(plan: dict, shots: dict) -> list[dict]:
    if (type(plan) is not dict or plan.get("schema") != "g1.benchmark-plan.v1"
            or plan.get("execution_mode") != "plan_only_no_paid_dispatch"
            or plan.get("model_generation_calls") != 0
            or plan.get("planned_tasks") != 9
            or type(plan.get("tasks")) is not list
            or len(plan["tasks"]) != 9):
        raise G1MetricError("G1 benchmark plan must be unexecuted and fixed-size")
    if (type(shots) is not dict or shots.get("schema") != "g1.fixed-shots.v1"
            or type(shots.get("shots")) is not list
            or len(shots["shots"]) != 3
            or tuple(s.get("shot_id") for s in shots["shots"])
            != EXPECTED_SHOTS):
        raise G1MetricError("Invalid G1 fixed-shot definitions")
    expected_pairs = [(sid, model) for sid in EXPECTED_SHOTS for model in EXPECTED_MODELS]
    actual_pairs = [(task.get("shot_id"), task.get("provider_model"))
                    for task in plan["tasks"] if type(task) is dict]
    if actual_pairs != expected_pairs:
        raise G1MetricError("Benchmark results must match nine original trial keys")
    for task in plan["tasks"]:
        if (task.get("attempt") != 1 or task.get("model_calls") != 0
                or task.get("is_real_ai_result") is not False
                or task.get("media_path") is not None
                or task.get("provider_task_id") is not None
                or task.get("actual_fee_usd") is not None):
            raise G1MetricError("Refusing to treat attempted tasks as unexecuted")
    return plan["tasks"]


def build_pending_results(plan: dict, shots: dict) -> dict:
    """Prepare nine explicit unanswered records; never fabricate scores."""
    tasks = _fixed_tasks(plan, shots)
    spoken_by_shot = {
        shot["shot_id"]: _shot_dialogue(shot["prompt"])
        for shot in shots["shots"]
    }
    return {
        "schema": "g1.benchmark-results.v1",
        "execution_mode": "offline_contract_only",
        "real_provider_calls": 0,
        "paid_provider_spend_usd": "0",
        "real_model_benchmark_complete": False,
        "transcriber_model": TRANSCRIBER_MODEL,
        "real_transcription_calls": 0,
        "artifacts_included": False,
        "total_trials": len(tasks),
        "results": [
            {
                "shot_id": task["shot_id"],
                "provider_model": task["provider_model"],
                "attempt": 1,
                "real_video_status": "not_generated",
                "video_sha256": None,
                "technical_qa": {
                    "status": "not_run",
                    "video_codec": None, "audio_codec": None,
                    "duration_seconds": None,
                    "width": None, "height": None,
                },
                "speech": {
                    "status": (
                        "not_applicable_silent_shot"
                        if not spoken_by_shot[task["shot_id"]]
                        else "waiting_for_real_transcription"
                    ),
                    "expected_characters": len(_characters(
                        spoken_by_shot[task["shot_id"]]
                    )),
                    "transcribed_characters": None,
                    "character_error_rate": None,
                    "character_accuracy": None,
                    "model": None,
                },
                "actual_fee_usd": None,
                "task_id": None,
                "human_approved": False,
            } for task in tasks
        ],
    }


def ffprobe_local_video(path: Path, expected_seconds: int) -> dict:
    """Local-only FFprobe, no URL, cloud/AI API or billable provider calls.

    Reports stream metadata; NOT a claim of model authenticity or good acting.
    """
    path = Path(path)
    if path.is_symlink() or not path.is_file() or path.suffix.lower() != ".mp4":
        raise G1MetricError("Expected an existing non-linked local MP4 file")
    if type(expected_seconds) is not int or not 3 <= expected_seconds <= 30:
        raise G1MetricError("Invalid G1 shot duration")
    try:
        # inspect_source provides basic duration, one video and content hash.
        inspected = inspect_source(path, expected_seconds)
        output = subprocess.run([
            "ffprobe", "-v", "error", "-show_entries",
            "format=duration:stream=codec_type,codec_name,width,height",
            "-of", "json", str(path),
        ], capture_output=True, text=True, check=True, timeout=30)
        parsed = json.loads(output.stdout)
        videos = [s for s in parsed.get("streams", [])
                  if s.get("codec_type") == "video"]
        audios = [s for s in parsed.get("streams", [])
                  if s.get("codec_type") == "audio"]
        if len(videos) != 1 or len(audios) > 1:
            raise G1MetricError("Invalid G1 video/audio stream count")
        width, height = videos[0].get("width"), videos[0].get("height")
        if (type(width) is not int or type(height) is not int
                or width <= 0 or height <= 0 or not math.isclose(
                    width / height, 9 / 16, rel_tol=0.055,
                )):
            raise G1MetricError("G1 video is not 9:16 portrait")
        return {
            "status": "offline_technical_probe_only",
            "video_codec": videos[0].get("codec_name"),
            "audio_codec": audios[0].get("codec_name") if audios else None,
            "duration_seconds": round(inspected["duration"], 3),
            "width": width, "height": height,
            "video_sha256": inspected["sha256"],
            "has_audio": inspected["has_audio"],
            "proves_real_ai_generation": False,
        }
    except (OSError, json.JSONDecodeError, KeyError, TypeError,
            MediaIngressError, subprocess.SubprocessError):
        raise G1MetricError("Local ffprobe technical validation failed") from None


def score_stub_transcript(expected: str, supplied: str) -> dict:
    """Exercise downstream text comparison without treating stub as real ASR."""
    return {
        "mode": "offline_stub_only",
        "transcriber_model": None,
        "measured_real_video": False,
        "diagnostic_character_error_rate": character_error_rate(expected, supplied),
        "real_character_error_rate": None,
        "real_character_accuracy": None,
    }
