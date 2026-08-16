from pathlib import Path

import pytest

from paddleboard_clipper.config import ClipperConfig


def test_from_env_requires_api_key(monkeypatch):
    monkeypatch.delenv("OPUS_API_KEY", raising=False)
    with pytest.raises(RuntimeError, match="OPUS_API_KEY"):
        ClipperConfig.from_env()


def test_from_env_applies_defaults(monkeypatch):
    monkeypatch.setenv("OPUS_API_KEY", "sk_test_123")
    for var in [
        "CLIPPER_WATCH_FOLDER",
        "CLIPPER_OUTPUT_FOLDER",
        "CLIPPER_TOPIC_KEYWORDS",
        "CLIPPER_CLIP_MIN_SECONDS",
    ]:
        monkeypatch.delenv(var, raising=False)

    config = ClipperConfig.from_env()

    assert config.opus_api_key == "sk_test_123"
    assert config.watch_folder == Path("raw_footage")
    assert config.output_folder == Path("clips")
    assert "paddleboarding" in config.topic_keywords
    assert config.clip_min_seconds == 15


def test_from_env_parses_overrides(monkeypatch):
    monkeypatch.setenv("OPUS_API_KEY", "sk_test_123")
    monkeypatch.setenv("CLIPPER_WATCH_FOLDER", "/mnt/footage")
    monkeypatch.setenv("CLIPPER_TOPIC_KEYWORDS", "surfing, kayaking")
    monkeypatch.setenv("CLIPPER_CLIP_MIN_SECONDS", "20")
    monkeypatch.setenv("CLIPPER_CLIP_MAX_SECONDS", "45")

    config = ClipperConfig.from_env()

    assert config.watch_folder == Path("/mnt/footage")
    assert config.topic_keywords == ("surfing", "kayaking")
    assert config.clip_min_seconds == 20
    assert config.clip_max_seconds == 45
