"""cowock CLI entrypoint.

Usage:
    python -m src.main run            # generate a product + marketing kit
    python -m src.main run --config path/to/config.yaml
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

# Allow running both as `python -m src.main` and `python src/main.py`.
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from src.agent import pipeline
from src.agent.config import load_config


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="cowock", description="Halal digital-products agent")
    sub = parser.add_subparsers(dest="command", required=True)

    run_p = sub.add_parser("run", help="generate a product + marketing kit")
    run_p.add_argument("--config", default=None, help="path to config.yaml")

    args = parser.parse_args(argv)

    if args.command == "run":
        cfg = load_config(args.config)
        pipeline.run(cfg)
        return 0

    parser.print_help()
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
