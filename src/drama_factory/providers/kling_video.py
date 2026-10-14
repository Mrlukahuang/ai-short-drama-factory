"""G1/R1.2 Kling 3.0 Omni one-task adapter, zero-call Fake.

Uses Kling's published /v1/videos/omni-video single task API.
No user account, key, paid call, OAuth, retries or new workflow is created.
Official reference: https://kling.ai/document-api/api/video/o1/video-omni/legacy
"""
from __future__ import annotations

import base64
import json
import os
import re
import time
from pathlib import Path
from urllib.parse import urlsplit
from urllib.request import Request, build_opener, HTTPRedirectHandler

from drama_factory.pipeline.media_ingest import inspect_source
from drama_factory.providers.video_provider import VideoRequest, VideoResult

MODEL_ID = "kling-v3-omni"
API_URL = "https://api-singapore.klingai.com/v1/videos/omni-video"
MAX_VIDEO_BYTES = 200 * 1024 * 1024


class KlingVideoDisabled(RuntimeError):
    pass


class KlingVideoResponseError(RuntimeError):
    pass


def _payload(request: VideoRequest, model_id: str) -> dict:
    if not re.fullmatch(r"kling-[a-zA-Z0-9_.-]{2,60}", model_id):
        raise KlingVideoDisabled("Invalid or unsupported Kling model identifier")
    if not 5 <= request.duration_seconds <= 15:
        raise KlingVideoDisabled("Kling 3 Omni contract limited to 5–15 seconds")
    if request.audio_reference is not None:
        # Kling accepts pre-registered voice asset elements, not local audio
        # files through this documented endpoint. Never drop a requested voice.
        raise KlingVideoDisabled("Local audio reference requires an approved voice asset API")
    if len(request.reference_images) > 4:
        raise KlingVideoDisabled("Offline contract limited to four images per shot")
    refs = []
    for path in request.reference_images:
        image = Path(path)
        if (image.is_symlink() or not image.is_file()
                or image.suffix.lower() not in (".png", ".jpg", ".jpeg", ".webp")
                or not 0 < image.stat().st_size <= 12 * 1024 * 1024):
            raise KlingVideoDisabled("Invalid Kling local image reference")
        refs.append({"image_url": base64.b64encode(image.read_bytes()).decode("ascii")})
    # Values mirror the *legacy official Omni endpoint*, not the newer text-only API.
    return {
        "model_name": model_id,
        "prompt": request.prompt,
        "image_list": refs,
        "duration": str(request.duration_seconds),
        "aspect_ratio": request.aspect_ratio,
        "mode": "pro",
        "sound": "on",
    }


def _http_json(method: str, url: str, key: str, payload: dict | None = None) -> dict:
    raw = None if payload is None else json.dumps(payload).encode("utf-8")
    req = Request(
        url, data=raw, method=method,
        headers={"Authorization": f"Bearer {key}", "Content-Type": "application/json"},
    )
    with build_opener().open(req, timeout=45) as resp:
        decoded = resp.read(2 * 1024 * 1024)
    result = json.loads(decoded)
    if type(result) is not dict:
        raise KlingVideoResponseError("Unexpected Kling JSON envelope")
    return result


def _download_kling_video(url: str, dest: Path) -> None:
    parsed = urlsplit(url)
    host = (parsed.hostname or "").lower()
    if (parsed.scheme != "https" or parsed.username or parsed.password
            or parsed.port is not None or parsed.fragment
            or not (host == "klingai.com" or host.endswith(".klingai.com"))):
        raise KlingVideoResponseError("Untrusted Kling video media URL")
    class NoRedirect(HTTPRedirectHandler):
        def redirect_request(self, req, fp, code, msg, headers, newurl):
            return None
    with build_opener(NoRedirect()).open(Request(url, method="GET"), timeout=45) as stream:
        with dest.open("xb") as out:
            size = 0
            while chunk := stream.read(1024 * 1024):
                size += len(chunk)
                if size > MAX_VIDEO_BYTES:
                    raise KlingVideoResponseError("Kling video exceeds local limit")
                out.write(chunk)


class FakeKlingVideoProvider:
    def __init__(self, model_id: str = MODEL_ID):
        self.model_id = model_id

    def generate_video(self, request: VideoRequest, destination: Path) -> VideoResult:
        _payload(request, self.model_id)
        return VideoResult(
            model_id=self.model_id, mp4_path=None, task_id=None,
            actual_fee_usd=None, model_calls=0, is_mock=True,
        )


class KlingVideoProvider:
    """Single documented submit, bounded poll and download (no retries).

    The VideoRequest's acknowledged spend is NOT a vendor-enforced USD limit;
    billing 'quota' amounts are not USD and never become actual_fee_usd.
    """

    def __init__(self, *, model_id: str = MODEL_ID, transport=None,
                 downloader=None, poll_interval: float = 5.0,
                 max_polls: int = 90):
        self.model_id = model_id
        self.transport = transport or _http_json
        self.downloader = downloader or _download_kling_video
        self.poll_interval = poll_interval
        self.max_polls = max_polls

    def generate_video(self, request: VideoRequest, destination: Path) -> VideoResult:
        if os.getenv("DRAMA_ENABLE_PAID_GENERATION") != "YES":
            raise KlingVideoDisabled("Paid Kling video generation disabled")
        if not request.operator_approved:
            raise KlingVideoDisabled("Explicit operator approval required")
        dest = Path(destination)
        if dest.exists() or dest.suffix.lower() != ".mp4":
            raise KlingVideoDisabled("Destination must be unused .mp4")
        payload = _payload(request, self.model_id)
        key = os.getenv("KLING_API_KEY")
        if not key:
            raise KlingVideoDisabled("KLING_API_KEY missing; no paid task submitted")
        response = self.transport("POST", API_URL, key, payload)
        if response.get("code") != 0:
            raise KlingVideoResponseError("Kling task submission rejected")
        task = response.get("data")
        task_id = task.get("task_id") if isinstance(task, dict) else None
        if not isinstance(task_id, str) or re.fullmatch(r"[A-Za-z0-9_-]{1,200}", task_id) is None:
            raise KlingVideoResponseError("Kling submission lacks valid task ID")
        for _ in range(self.max_polls):
            reply = self.transport("GET", f"{API_URL}/{task_id}", key)
            if reply.get("code") != 0 or not isinstance(reply.get("data"), dict):
                raise KlingVideoResponseError("Kling status query failed")
            status = reply["data"].get("task_status")
            if status == "succeed":
                result = reply["data"].get("task_result")
                videos = result.get("videos") if isinstance(result, dict) else None
                video_url = videos[0].get("url") if isinstance(videos, list) and videos and isinstance(videos[0], dict) else None
                if not isinstance(video_url, str) or not video_url:
                    raise KlingVideoResponseError("Kling finished without a video URL")
                dest.parent.mkdir(parents=True, exist_ok=True)
                try:
                    self.downloader(video_url, dest)
                    inspect_source(dest, request.duration_seconds)
                except Exception:
                    dest.unlink(missing_ok=True)
                    raise
                return VideoResult(
                    model_id=self.model_id, mp4_path=dest, task_id=task_id,
                    actual_fee_usd=None, model_calls=1, is_mock=False,
                )
            if status == "failed":
                raise KlingVideoResponseError("Kling task failed; never resubmit automatically")
            if status not in ("submitted", "processing"):
                raise KlingVideoResponseError("Unknown Kling task status")
            if self.poll_interval:
                time.sleep(self.poll_interval)
        raise KlingVideoResponseError("Kling polling expired; never submit again")
