"""Configuration for the social app.

Reads the optional ``social:`` block of ``config.yaml`` and falls back to
sensible defaults, so the app runs on a fresh clone with no setup.
"""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import yaml

ROOT = Path(__file__).resolve().parents[2]

DEFAULT_POSTING_TIMES = {
    # Local-time slots per platform; "default" is used for anything unlisted.
    "default": ["08:30", "12:30", "20:00"],
    "x": ["08:00", "12:00", "17:00", "20:30"],
    "instagram": ["11:00", "19:00"],
    "tiktok": ["07:00", "12:00", "21:00"],
    "youtube": ["16:00"],
    "linkedin": ["07:30", "12:00"],
    "facebook": ["09:00", "19:30"],
    "threads": ["09:00", "20:00"],
    "pinterest": ["14:00", "21:00"],
    "telegram": ["10:00", "18:00"],
}

DEFAULT_VIDEO = {
    "preset": "vertical",       # vertical | square | landscape
    "fps": 30,
    "seconds_per_scene": 3.4,
    "transition": 0.4,          # crossfade seconds (0 disables)
    "theme": "midnight",
    "voiceover": "none",        # none | espeak | elevenlabs
    "voice": "",
    "music": "",                # path to a background audio file
    "music_gain": -20.0,        # dB applied to the music bed
    "zoom": True,
}


@dataclass
class SocialConfig:
    timezone: str = "America/New_York"
    publish_mode: str = "dry_run"           # dry_run (preview) | live (MCP hand-off)
    auto_approve: bool = False
    require_media: bool = False
    default_platforms: list[str] = field(
        default_factory=lambda: ["x", "instagram", "tiktok", "linkedin"]
    )
    posting_times: dict[str, list[str]] = field(
        default_factory=lambda: dict(DEFAULT_POSTING_TIMES)
    )
    posts_per_day: int = 2
    hashtag_pool: list[str] = field(default_factory=list)
    video: dict[str, Any] = field(default_factory=lambda: dict(DEFAULT_VIDEO))
    llm: dict[str, Any] = field(
        default_factory=lambda: {
            "model": "claude-sonnet-5",
            "max_tokens": 4000,
            "temperature": 0.8,
        }
    )
    mcp: dict[str, Any] = field(
        default_factory=lambda: {
            "server": "Buffer",
            "tool": "create_post",
            "posting_type": "addToQueue",
            "channels": {},
        }
    )
    max_attempts: int = 3
    retry_backoff_seconds: int = 300
    db_path: str = "data/social.db"
    media_dir: str = "data/media"
    # Inherited from the top level of config.yaml so generated copy stays on-brand.
    brand: dict[str, Any] = field(default_factory=dict)
    niche: str = ""
    rules: dict[str, Any] = field(default_factory=dict)

    @property
    def live(self) -> bool:
        return self.publish_mode == "live"

    def resolve(self, relative: str) -> Path:
        p = Path(relative)
        return p if p.is_absolute() else ROOT / p

    def slots_for(self, platform: str) -> list[str]:
        return self.posting_times.get(platform) or self.posting_times.get(
            "default", DEFAULT_POSTING_TIMES["default"]
        )


def load_config(path: str | Path | None = None) -> SocialConfig:
    """Load ``config.yaml`` and build a :class:`SocialConfig`."""
    cfg_path = Path(path) if path else ROOT / "config.yaml"
    raw: dict[str, Any] = {}
    if cfg_path.exists():
        raw = yaml.safe_load(cfg_path.read_text(encoding="utf-8")) or {}

    block = dict(raw.get("social") or {})
    cfg = SocialConfig()

    for key in (
        "timezone",
        "publish_mode",
        "auto_approve",
        "require_media",
        "default_platforms",
        "posts_per_day",
        "hashtag_pool",
        "max_attempts",
        "retry_backoff_seconds",
        "db_path",
        "media_dir",
    ):
        if key in block and block[key] is not None:
            setattr(cfg, key, block[key])

    if block.get("posting_times"):
        cfg.posting_times = {**DEFAULT_POSTING_TIMES, **block["posting_times"]}
    if block.get("video"):
        cfg.video = {**DEFAULT_VIDEO, **block["video"]}
    if block.get("mcp"):
        cfg.mcp = {**cfg.mcp, **block["mcp"]}
    if block.get("llm"):
        cfg.llm = {**cfg.llm, **block["llm"]}

    # Brand context comes from the existing top-level config so the social app
    # and the product agent speak with the same voice.
    cfg.brand = raw.get("brand") or {}
    cfg.niche = raw.get("niche") or ""
    cfg.rules = raw.get("halal_rules") or {}

    # Env overrides win — handy for containers and cron.
    env_mode = os.environ.get("SOCIAL_PUBLISH_MODE")
    if env_mode:
        cfg.publish_mode = env_mode
    if os.environ.get("SOCIAL_DB_PATH"):
        cfg.db_path = os.environ["SOCIAL_DB_PATH"]
    if os.environ.get("SOCIAL_TIMEZONE"):
        cfg.timezone = os.environ["SOCIAL_TIMEZONE"]

    if cfg.publish_mode not in ("dry_run", "live"):
        raise ValueError(f"publish_mode must be 'dry_run' or 'live', got {cfg.publish_mode!r}")
    return cfg
