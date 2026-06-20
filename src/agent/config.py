"""Load and validate the agent configuration."""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import yaml

ROOT = Path(__file__).resolve().parents[2]
DEFAULT_CONFIG_PATH = ROOT / "config.yaml"


@dataclass
class Config:
    raw: dict[str, Any]

    @property
    def brand(self) -> dict[str, Any]:
        return self.raw.get("brand", {})

    @property
    def niche(self) -> str:
        return self.raw.get("niche", "").strip()

    @property
    def product_types(self) -> list[str]:
        return self.raw.get("product_types", ["ebook"])

    @property
    def channels(self) -> list[str]:
        return self.raw.get("channels", ["twitter"])

    @property
    def llm(self) -> dict[str, Any]:
        return self.raw.get("llm", {})

    @property
    def halal_rules(self) -> dict[str, Any]:
        return self.raw.get("halal_rules", {})

    @property
    def output_dir(self) -> Path:
        return ROOT / self.raw.get("output_dir", "products/output")

    @property
    def approvals_dir(self) -> Path:
        return ROOT / self.raw.get("approvals_dir", "approvals")

    def validate(self) -> None:
        if not self.niche:
            raise ValueError(
                "config.yaml: 'niche' is empty. Set a specific niche before running."
            )
        self.output_dir.mkdir(parents=True, exist_ok=True)
        self.approvals_dir.mkdir(parents=True, exist_ok=True)


def load_config(path: str | os.PathLike[str] | None = None) -> Config:
    cfg_path = Path(path) if path else DEFAULT_CONFIG_PATH
    if not cfg_path.exists():
        raise FileNotFoundError(f"Config not found: {cfg_path}")
    with cfg_path.open("r", encoding="utf-8") as fh:
        raw = yaml.safe_load(fh) or {}
    cfg = Config(raw=raw)
    cfg.validate()
    return cfg
