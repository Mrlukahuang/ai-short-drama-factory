"""G1/R1.1 Seedance 2.5 Volcengine Ark video adapter and credential-free Fake.

Official task API: POST /api/v3/contents/generations/tasks; GET task by ID.
No automatic resubmission, paid generation disabled by default.
See https://docs.volcengine.com/docs/ark/seedance-2-5 and
https://docs.volcengine.com/docs/ark/create-video-generation-task-api
"""
from __future__ import annotations

import base64
import os
import re
import time
from pathlib import Path
from urllib.parse import urlsplit
from urllib.request import Request, build_opener, HTTPRedirectHandler

from drama_factory.pipeline.media_ingest import inspect_source
from drama_factory.providers.video_provider import VideoProvider, VideoRequest, VideoResult

MODEL_ID = "doubao-seedance-2-5-260628"
ARK_BASE_URL = "https://ark.cn-beijing.volces.com/api/v3"
MAX_DOWNLOAD_BYTES = 200 * 1024 * 1024


class SeedanceVideoDisabled(RuntimeError):
    pass


class SeedanceVideoResponseError(RuntimeError):
    pass


def _data_uri(path: Path, extensions: dict[str, str], maximum_bytes: int) -> str:
    """Encode only bounded local files; never accept remote/local URL strings."""
    file = Path(path)
    if file.is_symlink() or not file.is_file() or file.suffix.lower() not in extensions:
        raise SeedanceVideoDisabled("Unsupported or linked local reference file")
    if not 0 < file.stat().st_size <= maximum_bytes:
        raise SeedanceVideoDisabled("Reference file outside provider input limit")
    data = file.read_bytes()
    return f"data:{extensions[file.suffix.lower()]};base64,{base64.b64encode(data).decode('ascii')}"


def _content(request: VideoRequest) -> list[dict]:
    if len(request.reference_images) > 30:
        raise SeedanceVideoDisabled("Seedance accepts at most 30 image references")
    payload: list[dict] = [{"type": "text", "text": request.prompt}]
    for file in request.reference_images:
        payload.append({
            "type": "image_url",
            "image_url": {"url": _data_uri(
                file, {".png": "image/png", ".jpg": "image/jpeg",
                       ".jpeg": "image/jpeg", ".webp": "image/webp"},
                30 * 1024 * 1024,
            )},
            "role": "reference_image",
        })
    if request.audio_reference is not None:
        payload.append({
            "type": "audio_url",
            "audio_url": {"url": _data_uri(
                request.audio_reference, {
                    ".wav": "audio/wav", ".mp3": "audio/mpeg",
                }, 15 * 1024 * 1024,
            )},
            "role": "reference_audio",
        })
    # The official Ark body max is 64 MiB (including base64 overhead).
    if sum(len(str(p)) for p in payload) > 60 * 1024 * 1024:
        raise SeedanceVideoDisabled("References exceed Ark request-size bound")
    return payload


def _download_verified_host(url: str, destination: Path) -> None:
    """Bound a one-time download to provider-controlled HTTPS media hosts."""
    parts = urlsplit(url)
    host = (parts.hostname or "").lower()
    if (parts.scheme != "https" or parts.username or parts.password
            or parts.port is not None or parts.fragment
            or not (host.endswith(".volces.com")
                    or host.endswith(".volcengine.com"))):
        raise SeedanceVideoResponseError("Untrusted video download URL")
    # Reject redirects to avoid a trusted provider URL being used as an SSRF hop.
    class NoRedirect(HTTPRedirectHandler):
        def redirect_request(self, req, fp, code, msg, headers, newurl):
            return None
    opener = build_opener(NoRedirect())
    response = opener.open(Request(url, method="GET"), timeout=45)
    try:
        with Path(destination).open("xb") as out:
            count = 0
            while chunk := response.read(1024 * 1024):
                count += len(chunk)
                if count > MAX_DOWNLOAD_BYTES:
                    raise SeedanceVideoResponseError("Video download exceeds size limit")
                out.write(chunk)
    finally:
        response.close()


class FakeSeedanceVideoProvider:
    """Same VideoProvider contract, never opens files, calls models or bills."""

    def generate_video(self, request: VideoRequest, destination: Path) -> VideoResult:
        _content(request)  # validate inputs exactly like live provider
        return VideoResult(
            model_id=MODEL_ID, mp4_path=None, task_id=None,
            actual_fee_usd=None, is_mock=True, model_calls=0,
        )


class SeedanceVideoProvider:
    """One optional official Ark submit + bounded status checks + media download.

    The acknowledgement in VideoRequest is NOT a server-side spend cap.
    No real charge is reported until independently verified against billing.
    """

    def __init__(self, client=None, *, downloader=None,
                 poll_interval: float = 5.0, max_polls: int = 90):
        self._client = client
        self._downloader = downloader or _download_verified_host
        self.poll_interval = poll_interval
        self.max_polls = max_polls

    def _client_or_raise(self):
        if self._client is not None:
            return self._client
        key = os.getenv("ARK_API_KEY")
        if not key:
            raise SeedanceVideoDisabled("ARK_API_KEY missing; no task submitted")
        try:
            from volcenginesdkarkruntime import Ark
        except ImportError as exc:
            raise SeedanceVideoDisabled(
                "Install optional volcengine-python-sdk[ark] to enable live calls"
            ) from exc
        return Ark(api_key=key, base_url=ARK_BASE_URL)

    def generate_video(self, request: VideoRequest, destination: Path) -> VideoResult:
        if os.getenv("DRAMA_ENABLE_PAID_GENERATION") != "YES":
            raise SeedanceVideoDisabled("Paid video generation disabled")
        if not request.operator_approved:
            raise SeedanceVideoDisabled("Explicit approval required for one paid request")
        dest = Path(destination)
        if dest.exists():
            raise SeedanceVideoDisabled("Refusing to overwrite an existing output")
        if dest.suffix.lower() != ".mp4":
            raise SeedanceVideoDisabled("Output must have .mp4 suffix")
        data = _content(request)  # validate refs before client and paid submission
        client = self._client_or_raise()
        # Official SDK: content_generation.tasks.create and .get(task_id=...).
        created = client.content_generation.tasks.create(
            model=MODEL_ID, content=data, duration=request.duration_seconds,
            ratio=request.aspect_ratio, output_format="mp4", generate_audio=True,
        )
        task_id = getattr(created, "id", None)
        if not isinstance(task_id, str) or not re.fullmatch(r"[A-Za-z0-9_-]{1,200}", task_id):
            raise SeedanceVideoResponseError("No valid Seedance task ID after submission")
        for _ in range(self.max_polls):
            state = client.content_generation.tasks.get(task_id=task_id)
            status = getattr(state, "status", None)
            if status == "succeeded":
                content = getattr(state, "content", None)
                url = getattr(content, "video_url", None)
                if not isinstance(url, str) or not url:
                    raise SeedanceVideoResponseError("Completed task missing MP4 URL")
                dest.parent.mkdir(parents=True, exist_ok=True)
                try:
                    self._downloader(url, dest)
                    inspect_source(dest, request.duration_seconds)
                except Exception:
                    dest.unlink(missing_ok=True)
                    raise
                return VideoResult(
                    model_id=MODEL_ID, mp4_path=dest, task_id=task_id,
                    actual_fee_usd=None, is_mock=False, model_calls=1,
                )
            if status in ("failed", "cancelled", "expired"):
                raise SeedanceVideoResponseError("Seedance task ended without video")
            if status not in ("queued", "running"):
                raise SeedanceVideoResponseError("Unknown Seedance task status")
            if self.poll_interval:
                time.sleep(self.poll_interval)
        raise SeedanceVideoResponseError("Seedance task polling expired; do not resubmit")
