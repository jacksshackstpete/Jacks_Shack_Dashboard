from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

SUPPORTED_VIDEO_EXTENSIONS = {".mp4", ".mov", ".m4v", ".avi", ".mkv", ".webm"}


def _float(env_val: str | None, default: float) -> float:
    return float(env_val) if env_val else default


def _int(env_val: str | None, default: int) -> int:
    return int(env_val) if env_val else default


@dataclass(frozen=True)
class ClipperConfig:
    """Runtime settings for the folder watcher and OpusClip client.

    Endpoint paths (opus_upload_endpoint / opus_projects_endpoint) are
    overridable via env vars so they can be corrected without a code change
    if OpusClip's live API differs from https://www.opus.pro/api at the time
    this was written.
    """

    opus_api_key: str
    opus_api_base: str = "https://api.opus.pro"
    opus_upload_endpoint: str = "/api/uploads"
    opus_projects_endpoint: str = "/api/clip-projects"

    watch_folder: Path = Path("raw_footage")
    output_folder: Path = Path("clips")
    processed_folder: Path = Path("raw_footage/_processed")
    failed_folder: Path = Path("raw_footage/_failed")
    state_file: Path = Path(".clipper/state.json")

    poll_interval_seconds: float = 15.0
    stability_checks: int = 2
    job_poll_timeout_seconds: float = 7200.0

    clip_min_seconds: int = 15
    clip_max_seconds: int = 60
    genre: str = "Auto"
    topic_keywords: tuple[str, ...] = (
        "paddleboarding",
        "stand up paddle board",
        "SUP",
        "Jack's Shack",
        "water sports",
    )
    brand_template_id: str | None = None

    @classmethod
    def from_env(cls) -> "ClipperConfig":
        api_key = os.environ.get("OPUS_API_KEY", "").strip()
        if not api_key:
            raise RuntimeError(
                "OPUS_API_KEY is not set. Add it to your environment or .env file "
                "(copy .env.example to .env and fill it in)."
            )

        keywords_env = os.environ.get("CLIPPER_TOPIC_KEYWORDS")
        keywords = (
            tuple(k.strip() for k in keywords_env.split(",") if k.strip())
            if keywords_env
            else cls.topic_keywords
        )

        return cls(
            opus_api_key=api_key,
            opus_api_base=os.environ.get("OPUS_API_BASE", cls.opus_api_base).rstrip("/"),
            opus_upload_endpoint=os.environ.get(
                "OPUS_UPLOAD_ENDPOINT", cls.opus_upload_endpoint
            ),
            opus_projects_endpoint=os.environ.get(
                "OPUS_PROJECTS_ENDPOINT", cls.opus_projects_endpoint
            ),
            watch_folder=Path(os.environ.get("CLIPPER_WATCH_FOLDER", cls.watch_folder)),
            output_folder=Path(os.environ.get("CLIPPER_OUTPUT_FOLDER", cls.output_folder)),
            processed_folder=Path(
                os.environ.get("CLIPPER_PROCESSED_FOLDER", cls.processed_folder)
            ),
            failed_folder=Path(os.environ.get("CLIPPER_FAILED_FOLDER", cls.failed_folder)),
            state_file=Path(os.environ.get("CLIPPER_STATE_FILE", cls.state_file)),
            poll_interval_seconds=_float(
                os.environ.get("CLIPPER_POLL_INTERVAL_SECONDS"), cls.poll_interval_seconds
            ),
            stability_checks=_int(
                os.environ.get("CLIPPER_STABILITY_CHECKS"), cls.stability_checks
            ),
            job_poll_timeout_seconds=_float(
                os.environ.get("CLIPPER_JOB_TIMEOUT_SECONDS"), cls.job_poll_timeout_seconds
            ),
            clip_min_seconds=_int(
                os.environ.get("CLIPPER_CLIP_MIN_SECONDS"), cls.clip_min_seconds
            ),
            clip_max_seconds=_int(
                os.environ.get("CLIPPER_CLIP_MAX_SECONDS"), cls.clip_max_seconds
            ),
            genre=os.environ.get("CLIPPER_GENRE", cls.genre),
            topic_keywords=keywords,
            brand_template_id=os.environ.get("OPUS_BRAND_TEMPLATE_ID") or cls.brand_template_id,
        )
