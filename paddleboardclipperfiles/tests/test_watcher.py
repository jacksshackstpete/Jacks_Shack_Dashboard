from pathlib import Path

from paddleboard_clipper.config import ClipperConfig
from paddleboard_clipper.watcher import FolderWatcher, _safe_filename


def make_config(tmp_path: Path) -> ClipperConfig:
    return ClipperConfig(
        opus_api_key="sk_test",
        watch_folder=tmp_path / "raw",
        output_folder=tmp_path / "clips",
        processed_folder=tmp_path / "raw" / "_processed",
        failed_folder=tmp_path / "raw" / "_failed",
        state_file=tmp_path / ".clipper" / "state.json",
        stability_checks=2,
    )


def test_growing_file_is_not_yet_ready(tmp_path):
    config = make_config(tmp_path)
    watcher = FolderWatcher(config)
    video = config.watch_folder / "dawn_patrol.mp4"
    video.write_bytes(b"a" * 100)

    assert watcher._stable_candidates() == []

    video.write_bytes(b"a" * 200)  # still growing
    assert watcher._stable_candidates() == []


def test_stable_file_becomes_ready_after_two_equal_checks(tmp_path):
    config = make_config(tmp_path)
    watcher = FolderWatcher(config)
    video = config.watch_folder / "dawn_patrol.mp4"
    video.write_bytes(b"a" * 100)

    assert watcher._stable_candidates() == []  # first sighting
    assert watcher._stable_candidates() == [video]  # size unchanged since


def test_non_video_files_are_ignored(tmp_path):
    config = make_config(tmp_path)
    watcher = FolderWatcher(config)
    (config.watch_folder / "notes.txt").write_text("not a video")

    assert watcher._stable_candidates() == []


def test_safe_filename_strips_unsafe_characters():
    assert _safe_filename("Epic Wipeout!! 🌊 / SUP") == "Epic_Wipeout_SUP"
    assert _safe_filename("") == "clip"
