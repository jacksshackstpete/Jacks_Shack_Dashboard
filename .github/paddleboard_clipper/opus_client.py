from __future__ import annotations

import logging
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import requests

from .config import ClipperConfig

logger = logging.getLogger(__name__)

_TERMINAL_FAILED_STATUSES = {"FAILED", "ERROR"}
_TERMINAL_DONE_STATUSES = {"DONE", "COMPLETED", "SUCCESS", "FINISHED"}

_CONTENT_TYPES = {
    ".mp4": "video/mp4",
    ".mov": "video/quicktime",
    ".m4v": "video/x-m4v",
    ".avi": "video/x-msvideo",
    ".mkv": "video/x-matroska",
    ".webm": "video/webm",
}


class OpusClipError(RuntimeError):
    """Raised when the OpusClip API returns an error or an unexpected response shape."""


@dataclass
class ClipResult:
    clip_id: str
    title: str
    download_url: str
    preview_url: str | None
    duration_seconds: float | None
    virality_score: float | None
    transcript_url: str | None
    raw: dict[str, Any]


class OpusClipClient:
    """Thin wrapper around the OpusClip (opus.pro) REST API.

    Handles: uploading a local file, kicking off an auto-clip + auto-caption
    project, polling until clips are rendered, and downloading the results.
    Captions are burned in by OpusClip itself as part of rendering (driven by
    brand_template_id) — there is no separate captioning step here.
    """

    def __init__(self, config: ClipperConfig, session: requests.Session | None = None):
        self.config = config
        self.session = session or requests.Session()
        self.session.headers.update(
            {
                "Authorization": f"Bearer {config.opus_api_key}",
                "Accept": "application/json",
            }
        )

    def _url(self, endpoint: str) -> str:
        return f"{self.config.opus_api_base}{endpoint}"

    def _request(self, method: str, endpoint: str, **kwargs: Any) -> dict[str, Any]:
        url = self._url(endpoint)
        resp = self.session.request(method, url, timeout=60, **kwargs)
        if not resp.ok:
            raise OpusClipError(f"{method} {url} failed with {resp.status_code}: {resp.text[:500]}")
        if not resp.content:
            return {}
        return resp.json()

    def upload_video(self, file_path: Path) -> str:
        """Upload a local video file and return a URL OpusClip can fetch it from."""
        upload_info = self._request(
            "POST",
            self.config.opus_upload_endpoint,
            json={"filename": file_path.name, "contentType": _guess_content_type(file_path)},
        )
        presigned_url = upload_info.get("presignedUrl") or upload_info.get("uploadUrl")
        file_url = upload_info.get("fileUrl") or upload_info.get("url")
        if not presigned_url or not file_url:
            raise OpusClipError(f"Unexpected upload response from OpusClip: {upload_info!r}")

        with file_path.open("rb") as fh:
            put_resp = requests.put(
                presigned_url,
                data=fh,
                headers={"Content-Type": _guess_content_type(file_path)},
                timeout=None,
            )
        if not put_resp.ok:
            raise OpusClipError(
                f"Uploading {file_path.name} to OpusClip storage failed with "
                f"{put_resp.status_code}: {put_resp.text[:500]}"
            )
        return file_url

    def create_clip_project(self, video_url: str, source_name: str) -> str:
        body: dict[str, Any] = {
            "videoUrl": video_url,
            "curationPref": {
                "clipDurations": [[self.config.clip_min_seconds, self.config.clip_max_seconds]],
                "topicKeywords": list(self.config.topic_keywords),
                "genre": self.config.genre,
            },
        }
        if self.config.brand_template_id:
            body["brandTemplateId"] = self.config.brand_template_id

        result = self._request("POST", self.config.opus_projects_endpoint, json=body)
        project_id = result.get("id") or result.get("projectId")
        if not project_id:
            raise OpusClipError(f"OpusClip did not return a project id for {source_name}: {result!r}")
        return str(project_id)

    def get_project(self, project_id: str) -> dict[str, Any]:
        return self._request("GET", f"{self.config.opus_projects_endpoint}/{project_id}")

    def wait_for_clips(self, project_id: str, source_name: str) -> list[ClipResult]:
        deadline = time.monotonic() + self.config.job_poll_timeout_seconds
        last_status = None
        while time.monotonic() < deadline:
            project = self.get_project(project_id)
            status = (project.get("status") or "").upper()
            if status != last_status:
                logger.info("OpusClip project %s (%s): status=%s", project_id, source_name, status)
                last_status = status

            if status in _TERMINAL_FAILED_STATUSES:
                raise OpusClipError(f"OpusClip project {project_id} for {source_name} failed: {project!r}")
            if status in _TERMINAL_DONE_STATUSES:
                return [_parse_clip(c) for c in project.get("clips") or []]

            time.sleep(self.config.poll_interval_seconds)

        raise OpusClipError(
            f"Timed out after {self.config.job_poll_timeout_seconds}s waiting on "
            f"OpusClip project {project_id} for {source_name}"
        )

    def download_clip(self, clip: ClipResult, destination: Path) -> Path:
        if not clip.download_url:
            raise OpusClipError(f"Clip {clip.clip_id!r} ({clip.title!r}) has no download URL")
        destination.parent.mkdir(parents=True, exist_ok=True)
        with self.session.get(clip.download_url, stream=True, timeout=120) as resp:
            resp.raise_for_status()
            with destination.open("wb") as fh:
                for chunk in resp.iter_content(chunk_size=1024 * 1024):
                    fh.write(chunk)
        return destination


def _guess_content_type(file_path: Path) -> str:
    return _CONTENT_TYPES.get(file_path.suffix.lower(), "application/octet-stream")


def _parse_clip(raw: dict[str, Any]) -> ClipResult:
    return ClipResult(
        clip_id=str(raw.get("id") or raw.get("clipId") or ""),
        title=raw.get("title") or raw.get("name") or "clip",
        download_url=raw.get("downloadUrl") or raw.get("videoUrl") or "",
        preview_url=raw.get("previewUrl"),
        duration_seconds=raw.get("duration") or raw.get("durationSeconds"),
        virality_score=raw.get("viralityScore") or raw.get("score"),
        transcript_url=raw.get("transcriptUrl") or raw.get("srtUrl"),
        raw=raw,
    )
