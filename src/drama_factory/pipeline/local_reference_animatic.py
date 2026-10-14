"""Offline animated storyboard shot from ONE operator-supplied reference still.

This is synthetic camera movement over a static user-provided image, NOT
real video footage or AI video. Requires BOTH existing Production approvals
and a separate explicit acknowledgement of this local derivative use.
No network, model call, real voice, model rights or publication authorization.
"""
from __future__ import annotations

from io import BytesIO
import shutil
import subprocess
from pathlib import Path
from tempfile import TemporaryDirectory

from PIL import Image, ImageDraw, ImageFont, ImageOps

from drama_factory.db import Database
from drama_factory.pipeline.local_asset_references import (
    LocalReferenceError, list_local_asset_references,
)
from drama_factory.pipeline.local_shot_media import (
    LocalShotMediaError, _scope, get_staged_shot_clips, stage_local_shot_video,
)

FRAME_WIDTH, FRAME_HEIGHT = 420, 746
MAX_ANIMATIC_SECONDS = 30
FRAME_RATE = 15


class LocalAnimaticError(ValueError):
    """Fixed error messages; do not leak local source image paths or bytes."""


def stage_reference_motion_clip(
    db: Database,
    *,
    series_id: str,
    production_id: str,
    shot_id: str,
    asset_id: str,
    reference_sha256: str,
    image_root: Path,
    media_root: Path,
    operator_confirmed_local_derivative_use: bool,
    replace_existing_video: bool = False,
) -> dict:
    """Render a watermark-labeled local simulated pan/zoom, stage as clip.

    Existing local shot clips are never silently replaced. Reuses the exact
    same staged media path and FFmpeg QA as separately uploaded video clips.
    """
    if operator_confirmed_local_derivative_use is not True:
        raise LocalAnimaticError("Explicit local derivative image use confirmation required")
    try:
        episode = _scope(db, series_id, production_id)
    except LocalShotMediaError:
        raise LocalAnimaticError("Production requires both approvals and matching series") from None
    if type(shot_id) is not str or type(asset_id) is not str:
        raise LocalAnimaticError("Invalid shot or reference asset")
    shot = next((s for s in episode.shots if s.shot_id == shot_id), None)
    if shot is None or not 1 <= shot.duration_seconds <= MAX_ANIMATIC_SECONDS:
        raise LocalAnimaticError("Unknown or overlong approved shot")
    if asset_id not in shot.character_ids and asset_id != shot.scene_id:
        raise LocalAnimaticError("Reference must be an on-shot actor or scene version")
    if (
        type(reference_sha256) is not str
        or len(reference_sha256) != 64
        or any(c not in "0123456789abcdef" for c in reference_sha256)
    ):
        raise LocalAnimaticError("Invalid selected reference digest")
    try:
        references = list_local_asset_references(db, series_id, asset_id, image_root)
        matched = [
            image for image in references if image["source_sha256"] == reference_sha256
        ]
    except (LocalReferenceError, OSError):
        raise LocalAnimaticError("Local reference readback verification failed") from None
    if len(matched) != 1:
        raise LocalAnimaticError("Selected reference not available or not verified")
    if matched[0]["kind"] not in ("actor", "scene"):
        raise LocalAnimaticError("Only on-shot actor or scene stills are supported")
    try:
        staged = get_staged_shot_clips(db, production_id, series_id, media_root)
    except (LocalShotMediaError, OSError):
        raise LocalAnimaticError("Existing local shot source failed verification") from None
    if shot_id in staged and replace_existing_video is not True:
        raise LocalAnimaticError("Explicit replacement of existing local video required")
    if shutil.which("ffmpeg") is None or shutil.which("ffprobe") is None:
        raise LocalAnimaticError("Local FFmpeg and FFprobe are required")
    with TemporaryDirectory(prefix="drama-local-animatic-") as tmp:
        work = Path(tmp)
        poster = work / "verified-still.png"
        output = work / "motion.mp4"
        try:
            with Image.open(BytesIO(matched[0]["png_bytes"])) as source:
                frame = ImageOps.fit(
                    source.convert("RGB"), (FRAME_WIDTH, FRAME_HEIGHT),
                    method=Image.Resampling.LANCZOS,
                )
            draw = ImageDraw.Draw(frame)
            draw.rectangle((0, 0, FRAME_WIDTH, 41), fill=(19, 27, 37))
            draw.rectangle(
                (0, FRAME_HEIGHT - 48, FRAME_WIDTH, FRAME_HEIGHT),
                fill=(19, 27, 37),
            )
            try:
                font = ImageFont.truetype("DejaVuSans.ttf", 17)
            except OSError:
                font = ImageFont.load_default()
            draw.text((13, 12), "LOCAL REFERENCE / SIMULATED MOTION",
                      fill="white", font=font)
            draw.text((13, FRAME_HEIGHT - 34), "NOT AI VIDEO / NOT FOR PUBLICATION",
                      fill="white", font=font)
            frame.save(poster, format="PNG")
            motion_filter = (
                "scale=420:746:force_original_aspect_ratio=increase,"
                "crop=420:746,"
                "zoompan=z='min(zoom+0.002,1.12)':d=1:"
                "x='(iw-iw/zoom)/2':y='(ih-ih/zoom)/2':"
                "s=360x640:fps=15,format=yuv420p"
            )
            command = [
                "ffmpeg", "-hide_banner", "-loglevel", "error", "-nostdin",
                "-y", "-loop", "1", "-framerate", str(FRAME_RATE),
                "-i", str(poster), "-vf", motion_filter,
                "-t", str(shot.duration_seconds), "-an",
                "-c:v", "libx264", "-preset", "ultrafast",
                "-pix_fmt", "yuv420p", "-r", str(FRAME_RATE),
                "-movflags", "+faststart", str(output),
            ]
            subprocess.run(
                command, check=True, capture_output=True,
                timeout=120, text=True,
            )
            if not output.is_file() or output.stat().st_size > 32 * 1024 * 1024:
                raise LocalAnimaticError("Local reference motion render exceeds limits")
            receipt = stage_local_shot_video(
                db, production_id, series_id, media_root,
                shot_id=shot_id, filename="reference-motion.mp4",
                content=output.read_bytes(),
                operator_attests_rights=True,
            )
        except (OSError, ValueError, subprocess.CalledProcessError,
                subprocess.TimeoutExpired, LocalShotMediaError):
            raise LocalAnimaticError("Local reference motion render or stage failed") from None
    return {
        **receipt, "kind": "simulated_reference_motion",
        "source_reference_sha256": reference_sha256,
        "source_asset_id": asset_id,
        "genuine_ai_video": False,
        "genuine_live_action": False,
        "rights_independently_verified": False,
        "publish_approved": False,
        "paid_api_calls": 0,
    }
