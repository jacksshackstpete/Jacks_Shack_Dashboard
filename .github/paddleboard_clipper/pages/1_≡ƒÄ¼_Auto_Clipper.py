from __future__ import annotations

import streamlit as st

try:
    from dotenv import load_dotenv

    load_dotenv()
except ImportError:
    pass

from paddleboard_clipper.config import ClipperConfig
from paddleboard_clipper.state import StateStore
from paddleboard_clipper.watcher import FolderWatcher

st.set_page_config(page_title="Auto Clipper", page_icon="🎬")
st.title("🎬 Paddleboard Auto Clipper")
st.caption(
    "Drop raw footage into the watch folder. The agent uploads it to OpusClip, "
    "which auto-generates short, captioned clips that get saved locally."
)

try:
    config = ClipperConfig.from_env()
except RuntimeError as exc:
    st.error(str(exc))
    st.info(
        "Set `OPUS_API_KEY` in your environment, a `.env` file, or "
        "`.streamlit/secrets.toml`, then reload this page."
    )
    st.stop()

col1, col2, col3 = st.columns(3)
col1.metric("Watch folder", str(config.watch_folder))
col2.metric("Output folder", str(config.output_folder))
col3.metric("Clip length", f"{config.clip_min_seconds}-{config.clip_max_seconds}s")

st.divider()

if st.button("🔍 Scan watch folder now", help="Runs one scan/processing pass synchronously."):
    watcher = FolderWatcher(config)
    with st.spinner("Scanning for new footage and talking to OpusClip..."):
        processed = watcher.scan_once()
    if processed:
        st.success(f"Processed {len(processed)} file(s).")
    else:
        st.info("No new, stable footage found.")

st.caption(
    "For continuous watching (recommended), run the agent as a background "
    "process instead of relying on this button: "
    "`uv run python -m paddleboard_clipper.agent`. See the README for details."
)

st.divider()
st.subheader("Recent jobs")

state = StateStore(config.state_file)
records = state.all_records()
if not records:
    st.info("No footage processed yet. Drop a video into the watch folder and scan.")
else:
    for record in records:
        status = record.get("status")
        icon = {"done": "✅", "failed": "❌"}.get(status, "⏳")
        with st.expander(f"{icon} {record['source_file']} — {status}"):
            st.write(f"Started: {record.get('started_at')}")
            if record.get("finished_at"):
                st.write(f"Finished: {record['finished_at']}")
            if record.get("error"):
                st.error(record["error"])
            for clip in record.get("clips", []):
                st.write(f"**{clip.get('title')}** — `{clip.get('file')}`")
                if clip.get("virality_score") is not None:
                    st.caption(f"Virality score: {clip['virality_score']}")
