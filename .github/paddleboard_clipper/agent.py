from __future__ import annotations

import argparse
import logging
import sys

try:
    from dotenv import load_dotenv
except ImportError:  # pragma: no cover - dotenv is a listed dependency
    load_dotenv = None

from .config import ClipperConfig
from .watcher import FolderWatcher


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="paddleboard-clipper",
        description="Watch a folder for raw paddleboard footage and auto-clip/caption it via OpusClip.",
    )
    parser.add_argument(
        "--once",
        action="store_true",
        help="Scan the watch folder a single time and exit, instead of running forever.",
    )
    parser.add_argument(
        "--log-level",
        default="INFO",
        choices=["DEBUG", "INFO", "WARNING", "ERROR"],
    )
    args = parser.parse_args(argv)

    logging.basicConfig(
        level=args.log_level,
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    )

    if load_dotenv is not None:
        load_dotenv()

    try:
        config = ClipperConfig.from_env()
    except RuntimeError as exc:
        print(f"Configuration error: {exc}", file=sys.stderr)
        return 1

    watcher = FolderWatcher(config)
    if args.once:
        processed = watcher.scan_once()
        print(f"Processed {len(processed)} file(s).")
    else:
        watcher.run_forever()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
