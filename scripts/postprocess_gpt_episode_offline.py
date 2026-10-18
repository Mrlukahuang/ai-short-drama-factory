"""G4/R4.4: offline post-process a completed REAL 12-shot preview.

Remux screenplay-timed DRAFT Chinese subtitle cues into the existing video
while stream-copying its original H264 video and native AAC audio. No model,
TTS, transcription, paid calls, new music or publication approval.
"""
from __future__ import annotations

import argparse
from datetime import date
from decimal import Decimal
import hashlib
import json
from pathlib import Path
import re
import subprocess

from assemble_gpt_video_three import probe, sha
from drama_factory.pipeline.offline_qa import _verify_muxed_subtitles
from drama_factory.pipeline.screenplay import Screenplay

IDS = [f"s{i:02}" for i in range(1, 13)]
HEX = re.compile(r"[a-f0-9]{64}\Z")


def _input_file(path: Path) -> Path:
    if path.is_symlink() or not path.is_file() or path.stat().st_size > 512 * 1024 * 1024:
        raise ValueError("Regular bounded existing input file required")
    return path


def _write_json(path: Path, data: dict) -> None:
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
                    encoding="utf-8")


def _stamp(milliseconds: int) -> str:
    hours, rem = divmod(milliseconds, 3_600_000)
    minutes, rem = divmod(rem, 60_000)
    seconds, ms = divmod(rem, 1_000)
    return f"{hours:02}:{minutes:02}:{seconds:02},{ms:03}"


def _draft_captions(screenplay: Screenplay, records: list[dict]) -> tuple[str, int]:
    """Timing is scaled from script to generated clip durations; NOT ASR."""
    if [s.shot_id for s in screenplay.shots] != IDS or len(records) != 12:
        raise ValueError("Script and completed shot IDs differ")
    cues = []
    elapsed = Decimal(0)
    for shot, record in zip(screenplay.shots, records, strict=True):
        duration = Decimal(str(record["duration_seconds"]))
        if not 3 <= duration <= Decimal("10.1"):
            raise ValueError("Shot duration outside recorded bounds")
        count = len(shot.dialogue)
        for index, cue in enumerate(shot.dialogue):
            if cue.start_second is None:
                start_frac = Decimal(index) / Decimal(count)
                end_frac = Decimal(index + 1) / Decimal(count)
            else:
                start_frac = Decimal(cue.start_second) / Decimal(shot.duration_seconds)
                end_frac = Decimal(cue.end_second) / Decimal(shot.duration_seconds)
            start = round((elapsed + start_frac * duration) * 1000)
            end = round((elapsed + end_frac * duration) * 1000)
            if start >= end or (cues and start < cues[-1][1]):
                raise ValueError("Overlapping or empty derived subtitle slot")
            text = " ".join(cue.text.split())
            if not text:
                raise ValueError("Empty screenplay dialogue")
            cues.append((start, end, text))
        elapsed += duration
    if not cues:
        raise ValueError("No screenplay dialogue; subtitle draft cannot be fabricated")
    blocks = [f"{i}\n{_stamp(start)} --> {_stamp(end)}\n{line}"
              for i, (start, end, line) in enumerate(cues, 1)]
    return "\n\n".join(blocks) + "\n", len(cues)


def _verified_screenplay(writer_dir: Path) -> tuple[Screenplay, str]:
    """Reuse the original fixed real Sol response integrity/validation protocol."""
    from prepare_writer_comparison import case_inputs
    from run_gpt_video_three import SOURCE_HASH
    from drama_factory.pipeline.writer_execution_prep import prepare_request, parse_response

    path = _input_file(Path(writer_dir) / "gpt-6.1-sol.response.json")
    if path.stat().st_size > 8 * 1024 * 1024:
        raise ValueError("Original bounded writer artifact required")
    raw = json.loads(path.read_text("utf-8"))
    canonical = json.dumps(raw, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    if hashlib.sha256(canonical.encode()).hexdigest() != SOURCE_HASH:
        raise ValueError("Writer response is not the original approved source")
    req, ctx = case_inputs("misunderstanding")
    parsed = parse_response(prepare_request("gpt-6.1-sol", req, ctx), raw,
                            on=date(2026, 10, 17), simulated=False)
    if parsed.status != "validated_draft" or parsed.screenplay is None:
        raise ValueError("Original screenplay validation failed")
    return parsed.screenplay, SOURCE_HASH


def render_draft_postprocess(screenplay: Screenplay, source_hash: str,
                             episode_dir: Path, delivery_dir: Path,
                             output_dir: Path) -> dict:
    """Existing media only; never modify prior successful 12-shot delivery."""
    episode_dir, delivery_dir, output_dir = map(Path, (episode_dir, delivery_dir, output_dir))
    if any(p.is_symlink() for p in (episode_dir, delivery_dir, output_dir)):
        raise ValueError("Linked media/output directory denied")
    if not isinstance(source_hash, str) or not HEX.fullmatch(source_hash):
        raise ValueError("Invalid screenplay provenance hash")
    report_path = _input_file(episode_dir / "report.json")
    delivery_path = _input_file(delivery_dir / "delivery.json")
    preview = _input_file(delivery_dir / "gpt-episode-preview.mp4")
    report = json.loads(report_path.read_text("utf-8"))
    delivery = json.loads(delivery_path.read_text("utf-8"))
    records = report.get("shots")
    if (report.get("status") != "episode_clips_completed_pending_human_review"
            or report.get("source_response_sha256") != source_hash
            or report.get("generation_attempts") != 9
            or report.get("reused_shot_ids") != IDS[:3]
            or type(records) is not list or len(records) != 12
            or [s.get("shot_id") for s in records if type(s) is dict] != IDS
            or delivery.get("shot_order") != IDS
            or delivery.get("source_report_sha256") != sha(report_path)
            or delivery.get("source_response_sha256") != source_hash
            or delivery.get("mp4_sha256") != sha(preview)
            or delivery.get("full_decode_passed") is not True
            or delivery.get("all_script_shots_assembled") is not True
            or delivery.get("publish_approved") is not False):
        raise ValueError("Verified full-episode delivery and report required")
    # Check every original source file as well as the existing delivery.
    signature = None
    for record in records:
        path = _input_file(episode_dir / (record["shot_id"] + ".mp4"))
        if sha(path) != record.get("video_sha256"):
            raise ValueError("Original clip no longer matches its receipt")
        details = probe(path)
        if abs(details["duration_seconds"] - float(record["duration_seconds"])) > .1:
            raise ValueError("Original clip duration changed")
        if signature is not None and details["stream_signature"] != signature:
            raise ValueError("Incompatible original clip streams")
        signature = details["stream_signature"]
    original_media = probe(preview)
    if original_media["stream_signature"] != signature:
        raise ValueError("Original assembled stream mismatch")
    srt, count = _draft_captions(screenplay, records)

    resolved_output = output_dir.resolve()
    if (output_dir.exists() or episode_dir.resolve() == resolved_output
            or episode_dir.resolve() in resolved_output.parents
            or delivery_dir.resolve() == resolved_output
            or delivery_dir.resolve() in resolved_output.parents):
        raise ValueError("Fresh output outside source directories required")
    output_dir.mkdir(parents=True, exist_ok=False)
    subtitles = output_dir / "draft-captions.srt"
    subtitles.write_text(srt, encoding="utf-8")
    final = output_dir / "gpt-episode-caption-draft.mp4"
    subprocess.run([
        "ffmpeg", "-hide_banner", "-loglevel", "error", "-nostdin", "-n",
        "-i", str(preview), "-i", str(subtitles),
        "-map", "0:v:0", "-map", "0:a:0", "-map", "1:0",
        "-c:v", "copy", "-c:a", "copy", "-c:s", "mov_text",
        "-movflags", "+faststart", str(final),
    ], check=True, capture_output=True, timeout=120)
    final_media = probe(final)
    if (abs(final_media["duration_seconds"] - original_media["duration_seconds"]) > .3
            or final_media["stream_signature"] != original_media["stream_signature"]):
        raise ValueError("Post-production changed original A/V stream characteristics")
    subtitle_count = _verify_muxed_subtitles(final, subtitles)
    if subtitle_count != count:
        raise ValueError("Embedded subtitle track differs from draft captions")
    subprocess.run([
        "ffmpeg", "-hide_banner", "-loglevel", "error", "-xerror", "-nostdin",
        "-i", str(final), "-map", "0:v:0", "-map", "0:a:0",
        "-f", "null", "-"
    ], check=True, capture_output=True, timeout=120)
    digest = sha(final)
    metadata = {
        "06_dialogue": {"step": "06_dialogue", "route": "existing_model_native_audio",
                        "audio_stream_preserved": True, "speech_text_verified": False},
        "07_subtitles": {"step": "07_subtitles", "status": "screenplay_timed_draft_not_asr",
                          "source": "validated_screenplay_estimated_scaled_clip_timing",
                          "srt_sha256": sha(subtitles), "subtitle_cues": count,
                          "actual_speech_alignment_verified": False},
        "08_music": {"step": "08_music", "route": "existing_native_audio_unchanged",
                     "separate_music_added": False},
        "09_render": {"step": "09_render", "file_name": final.name,
                      "mp4_sha256": digest, "original_mp4_sha256": sha(preview),
                      "video_stream_copy": True, "audio_stream_copy": True},
        "10_qa": {"step": "10_qa", "technical_decode_passed": True,
                  "embedded_draft_subtitles_verified": True,
                  "subtitle_cue_count": count, "mp4_sha256": digest,
                  "source_response_sha256": source_hash,
                  "original_source_report_sha256": sha(report_path),
                  "new_model_calls": 0, "new_api_cost_usd": "0",
                  "visual_quality_verified": False,
                  "dialogue_content_verified": False,
                  "subtitle_alignment_verified": False,
                  "full_episode_complete": False, "publish_approved": False},
    }
    for step, data in metadata.items():
        _write_json(output_dir / (step + ".json"), data)
    return {"output_mp4": str(final), "subtitle_cues": count,
            "mp4_sha256": digest, **metadata["10_qa"]}


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--writer-dir", type=Path, required=True)
    parser.add_argument("--episode-dir", type=Path, required=True)
    parser.add_argument("--delivery-dir", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    args = parser.parse_args(argv)
    screenplay, source_hash = _verified_screenplay(args.writer_dir)
    result = render_draft_postprocess(screenplay, source_hash,
                                      args.episode_dir, args.delivery_dir, args.output_dir)
    print(json.dumps(result, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
