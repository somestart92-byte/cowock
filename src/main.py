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

from src.agent import market_research, pipeline
from src.agent.config import load_config
from src.agent.llm import LLM


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="cowock", description="Halal digital-products agent")
    sub = parser.add_subparsers(dest="command", required=True)

    run_p = sub.add_parser("run", help="generate a product + marketing kit")
    run_p.add_argument("--config", default=None, help="path to config.yaml")

    res_p = sub.add_parser("research", help="run market research only")
    res_p.add_argument("--config", default=None, help="path to config.yaml")

    args = parser.parse_args(argv)

    if args.command == "run":
        cfg = load_config(args.config)
        pipeline.run(cfg)
        return 0

    if args.command == "research":
        cfg = load_config(args.config)
        llm = LLM(
            model=cfg.llm.get("model", "claude-opus-4-8"),
            max_tokens=cfg.llm.get("max_tokens", 4000),
            temperature=cfg.llm.get("temperature", 0.7),
        )
        report = market_research.research(cfg.niche, cfg.brand, llm, notes=cfg.research_notes)
        print(report.to_markdown())
        return 0

    parser.print_help()
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
