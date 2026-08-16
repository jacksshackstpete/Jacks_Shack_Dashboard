from __future__ import annotations

import logging
import time
from pathlib import Path

from .config import SUPPORTED_VIDEO_EXTENSIONS, ClipperConfig
from .opus_client import OpusClipClient, OpusClipError
from .state import JobRecord, StateStore, now_iso

logger = logging.getLogger(__name__)


class FolderWatcher:
    """Polls a folder for raw footage, and once a file stops growing (i.e. the
    copy/upload into the folder has finished), sends it through OpusClip and
    saves the resulting short, captioned clips."""

    def __init__(
        self,
        config: ClipperConfig,
        client: OpusClipClient | None = None,
        state: StateStore | None = None,
    ):
        self.config = config
        self.client = client or OpusClipClient(config)
        self.state = state or StateStore(config.state_file)
        self._size_history: dict[Path, list[int]] = {}

        for folder in (
            config.watch_folder,
            config.output_folder,
            config.processed_folder,
            config.failed_folder,
        ):
            folder.mkdir(parents=True, exist_ok=True)

    def scan_once(self) -> list[Path]:
        """Process any stable, not-yet-processed videos currently in the watch
        folder. Returns the files processed on this pass."""
        processed: list[Path] = []
        for candidate in self._stable_candidates():
            self._process_file(candidate)
            processed.append(candidate)
        return processed

    def run_forever(self) -> None:
        logger.info(
            "Watching %s for raw paddleboard footage (poll every %.0fs)",
            self.config.watch_folder,
            self.config.poll_interval_seconds,
        )
        while True:
            try:
                self.scan_once()
            except Exception:
                logger.exception("Unexpected error during watch loop; continuing")
            time.sleep(self.config.poll_interval_seconds)

    def _stable_candidates(self) -> list[Path]:
        ready: list[Path] = []
        seen: set[Path] = set()

        for path in sorted(self.config.watch_folder.iterdir()):
            if not path.is_file() or path.suffix.lower() not in SUPPORTED_VIDEO_EXTENSIONS:
                continue
            seen.add(path)
            if self.state.is_processed(str(path)):
                continue

            size = path.stat().st_size
            history = self._size_history.setdefault(path, [])
            history.append(size)
            history[:] = history[-self.config.stability_checks :]

            if len(history) >= self.config.stability_checks and len(set(history)) == 1:
                ready.append(path)

        for tracked in list(self._size_history):
            if tracked not in seen:
                del self._size_history[tracked]

        return ready

    def _process_file(self, path: Path) -> None:
        logger.info("Processing new footage: %s", path.name)
        record = JobRecord(source_file=str(path), status="uploading", started_at=now_iso())
        self.state.upsert(record)

        try:
            video_url = self.client.upload_video(path)
            record.status = "processing"
            self.state.upsert(record)

            project_id = self.client.create_clip_project(video_url, path.name)
            clips = self.client.wait_for_clips(project_id, path.name)

            clip_dir = self.config.output_folder / path.stem
            saved = []
            for i, clip in enumerate(clips, start=1):
                dest = clip_dir / f"{i:02d}_{_safe_filename(clip.title)}.mp4"
                self.client.download_clip(clip, dest)
                saved.append(
                    {
                        "title": clip.title,
                        "file": str(dest),
                        "duration_seconds": clip.duration_seconds,
                        "virality_score": clip.virality_score,
                    }
                )
                logger.info("Saved clip: %s", dest)

            record.status = "done"
            record.clips = saved
            record.finished_at = now_iso()
            self.state.upsert(record)
            self._archive(path, self.config.processed_folder)

        except OpusClipError as exc:
            logger.error("Failed to process %s: %s", path.name, exc)
            self._mark_failed(record, path, str(exc))
        except Exception as exc:  # keep the watch loop alive on unexpected errors
            logger.exception("Unexpected error processing %s", path.name)
            self._mark_failed(record, path, f"unexpected error: {exc}")

    def _mark_failed(self, record: JobRecord, path: Path, error: str) -> None:
        record.status = "failed"
        record.error = error
        record.finished_at = now_iso()
        self.state.upsert(record)
        self._archive(path, self.config.failed_folder)

    def _archive(self, path: Path, folder: Path) -> None:
        folder.mkdir(parents=True, exist_ok=True)
        destination = folder / path.name
        if destination.exists():
            destination = folder / f"{path.stem}_{int(time.time())}{path.suffix}"
        path.rename(destination)
        self._size_history.pop(path, None)


def _safe_filename(name: str) -> str:
    keep = "-_ "
    cleaned = "".join(c for c in name if c.isalnum() or c in keep)
    collapsed = "_".join(cleaned.split())
    return (collapsed or "clip")[:80]
