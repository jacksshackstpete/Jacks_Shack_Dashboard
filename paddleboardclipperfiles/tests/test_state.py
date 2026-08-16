from paddleboard_clipper.state import JobRecord, StateStore, now_iso


def test_new_file_is_not_processed(tmp_path):
    state = StateStore(tmp_path / "state.json")
    assert state.is_processed("foo.mp4") is False


def test_upsert_and_query(tmp_path):
    state = StateStore(tmp_path / "state.json")
    record = JobRecord(source_file="foo.mp4", status="processing", started_at=now_iso())
    state.upsert(record)
    assert state.is_processed("foo.mp4") is False  # not terminal yet

    record.status = "done"
    record.clips = [{"title": "Big Wave", "file": "clips/foo/01_Big_Wave.mp4"}]
    state.upsert(record)

    assert state.is_processed("foo.mp4") is True
    records = state.all_records()
    assert len(records) == 1
    assert records[0]["clips"][0]["title"] == "Big Wave"


def test_failed_status_counts_as_processed(tmp_path):
    state = StateStore(tmp_path / "state.json")
    record = JobRecord(source_file="bad.mp4", status="failed", started_at=now_iso(), error="boom")
    state.upsert(record)
    assert state.is_processed("bad.mp4") is True
