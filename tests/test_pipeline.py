"""Smoke tests — run the full pipeline in DRY-RUN (no API key needed)."""

import json
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from src.agent import compliance
from src.agent.config import load_config
from src.agent.llm import LLM
from src.agent.pipeline import run


def _dry_run_env():
    os.environ.pop("ANTHROPIC_API_KEY", None)


def test_pipeline_dry_run_creates_artifacts():
    _dry_run_env()
    cfg = load_config()
    run_dir = run(cfg)
    assert (run_dir / "product.md").exists()
    assert (run_dir / "marketing.md").exists()
    meta = json.loads((run_dir / "meta.json").read_text())
    assert "product" in meta and "compliance" in meta
    approval = cfg.approvals_dir / f"{run_dir.name}.json"
    assert approval.exists()
    assert json.loads(approval.read_text())["approved"] is False


def test_compliance_flags_red_flags():
    _dry_run_env()
    llm = LLM(model="claude-opus-4-8")
    bad = compliance.review("Earn guaranteed returns from our casino!", {}, llm)
    assert bad.ok is False
    good = compliance.review("A practical halal productivity guide.", {}, llm)
    assert good.ok is True


if __name__ == "__main__":
    test_pipeline_dry_run_creates_artifacts()
    test_compliance_flags_red_flags()
    print("OK")
