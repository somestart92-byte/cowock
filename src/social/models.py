"""Core data types for the social automation app.

Everything that is persisted is a plain dataclass with ``to_row``/``from_row``
helpers so the storage layer stays a thin SQLite wrapper.
"""

from __future__ import annotations

import json
import uuid
from dataclasses import dataclass, field, asdict
from datetime import datetime, timezone
from typing import Any

UTC = timezone.utc

PLATFORMS = (
    "x",
    "instagram",
    "tiktok",
    "youtube",
    "linkedin",
    "facebook",
    "threads",
    "pinterest",
    "telegram",
)

# Hard platform limits used by the generator and the pre-flight validator.
LIMITS: dict[str, dict[str, Any]] = {
    "x": {"chars": 280, "hashtags": 3, "media": 4, "video_seconds": 140},
    "instagram": {"chars": 2200, "hashtags": 30, "media": 10, "video_seconds": 90},
    "threads": {"chars": 500, "hashtags": 5, "media": 10, "video_seconds": 300},
    "tiktok": {"chars": 2200, "hashtags": 8, "media": 1, "video_seconds": 600},
    "youtube": {"chars": 5000, "hashtags": 15, "media": 1, "video_seconds": 60},
    "linkedin": {"chars": 3000, "hashtags": 5, "media": 9, "video_seconds": 600},
    "facebook": {"chars": 5000, "hashtags": 10, "media": 10, "video_seconds": 7200},
    "pinterest": {"chars": 500, "hashtags": 8, "media": 1, "video_seconds": 900},
    "telegram": {"chars": 1024, "hashtags": 10, "media": 10, "video_seconds": 3600},
}

# Lifecycle. Only `approved` posts are ever picked up by the publisher.
DRAFT = "draft"
APPROVED = "approved"
HANDOFF = "handoff"      # job emitted, waiting for the MCP agent to run it
PUBLISHED = "published"
FAILED = "failed"
CANCELLED = "cancelled"
STATUSES = (DRAFT, APPROVED, HANDOFF, PUBLISHED, FAILED, CANCELLED)


def now_iso() -> str:
    return datetime.now(UTC).replace(microsecond=0).isoformat()


def new_id(prefix: str) -> str:
    return f"{prefix}_{uuid.uuid4().hex[:12]}"


def _loads(value: Any, fallback: Any) -> Any:
    if value in (None, ""):
        return fallback
    if isinstance(value, (list, dict)):
        return value
    try:
        return json.loads(value)
    except (TypeError, ValueError):
        return fallback


@dataclass
class MediaAsset:
    """A file attached to a post. ``path`` is relative to the repo root."""

    path: str
    kind: str = "image"  # image | video
    alt: str = ""

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "MediaAsset":
        return cls(
            path=data.get("path", ""),
            kind=data.get("kind", "image"),
            alt=data.get("alt", ""),
        )


@dataclass
class Account:
    """A destination: one platform profile the app can publish to."""

    platform: str
    handle: str
    id: str = field(default_factory=lambda: new_id("acct"))
    display_name: str = ""
    enabled: bool = True
    # Adapter-specific routing (Buffer channel id, IG user id, YT channel...).
    settings: dict[str, Any] = field(default_factory=dict)
    created_at: str = field(default_factory=now_iso)

    def to_row(self) -> tuple:
        return (
            self.id,
            self.platform,
            self.handle,
            self.display_name,
            int(self.enabled),
            json.dumps(self.settings),
            self.created_at,
        )

    @classmethod
    def from_row(cls, row: Any) -> "Account":
        return cls(
            id=row["id"],
            platform=row["platform"],
            handle=row["handle"],
            display_name=row["display_name"] or "",
            enabled=bool(row["enabled"]),
            settings=_loads(row["settings"], {}),
            created_at=row["created_at"],
        )


@dataclass
class Post:
    """One piece of content aimed at one platform at one point in time."""

    platform: str
    body: str
    id: str = field(default_factory=lambda: new_id("post"))
    account_id: str | None = None
    campaign: str = "default"
    title: str = ""           # YouTube title / Pinterest title
    hashtags: list[str] = field(default_factory=list)
    media: list[MediaAsset] = field(default_factory=list)
    link: str = ""
    first_comment: str = ""
    scheduled_at: str = field(default_factory=now_iso)
    status: str = DRAFT
    attempts: int = 0
    error: str = ""
    external_id: str = ""     # id returned by the platform
    external_url: str = ""
    published_at: str = ""
    source: str = "manual"    # manual | generated | product
    meta: dict[str, Any] = field(default_factory=dict)
    created_at: str = field(default_factory=now_iso)
    updated_at: str = field(default_factory=now_iso)

    # -- derived ---------------------------------------------------------
    @property
    def full_text(self) -> str:
        parts = [self.body.strip()]
        if self.link:
            parts.append(self.link.strip())
        if self.hashtags:
            parts.append(" ".join(f"#{h.lstrip('#')}" for h in self.hashtags))
        return "\n\n".join(p for p in parts if p)

    def limits(self) -> dict[str, Any]:
        return LIMITS.get(self.platform, {"chars": 2200, "hashtags": 10, "media": 10})

    def validate(self) -> list[str]:
        """Return a list of human-readable problems (empty means good to go)."""
        problems: list[str] = []
        limits = self.limits()
        if not self.body.strip():
            problems.append("body is empty")
        if len(self.full_text) > limits["chars"]:
            problems.append(
                f"{len(self.full_text)} chars exceeds the {self.platform} limit of {limits['chars']}"
            )
        if len(self.hashtags) > limits["hashtags"]:
            problems.append(
                f"{len(self.hashtags)} hashtags exceeds the {self.platform} limit of {limits['hashtags']}"
            )
        if len(self.media) > limits["media"]:
            problems.append(
                f"{len(self.media)} attachments exceeds the {self.platform} limit of {limits['media']}"
            )
        if self.platform in ("tiktok", "youtube") and not any(
            m.kind == "video" for m in self.media
        ):
            problems.append(f"{self.platform} requires a video attachment")
        if self.platform == "instagram" and not self.media:
            problems.append("instagram requires at least one image or video")
        for asset in self.media:
            if not asset.path:
                problems.append("an attachment has no file path")
        return problems

    def to_row(self) -> tuple:
        return (
            self.id,
            self.account_id,
            self.platform,
            self.campaign,
            self.title,
            self.body,
            json.dumps(self.hashtags),
            json.dumps([m.to_dict() for m in self.media]),
            self.link,
            self.first_comment,
            self.scheduled_at,
            self.status,
            self.attempts,
            self.error,
            self.external_id,
            self.external_url,
            self.published_at,
            self.source,
            json.dumps(self.meta),
            self.created_at,
            self.updated_at,
        )

    @classmethod
    def from_row(cls, row: Any) -> "Post":
        return cls(
            id=row["id"],
            account_id=row["account_id"],
            platform=row["platform"],
            campaign=row["campaign"],
            title=row["title"] or "",
            body=row["body"] or "",
            hashtags=_loads(row["hashtags"], []),
            media=[MediaAsset.from_dict(m) for m in _loads(row["media"], [])],
            link=row["link"] or "",
            first_comment=row["first_comment"] or "",
            scheduled_at=row["scheduled_at"],
            status=row["status"],
            attempts=row["attempts"] or 0,
            error=row["error"] or "",
            external_id=row["external_id"] or "",
            external_url=row["external_url"] or "",
            published_at=row["published_at"] or "",
            source=row["source"] or "manual",
            meta=_loads(row["meta"], {}),
            created_at=row["created_at"],
            updated_at=row["updated_at"],
        )

    def to_dict(self) -> dict[str, Any]:
        data = asdict(self)
        data["media"] = [m.to_dict() for m in self.media]
        return data


@dataclass
class PublishResult:
    """Outcome of a publish attempt.

    ``pending`` marks the MCP hand-off case: the job was emitted for the agent
    to run through its connected MCP tools and is not live yet.
    """

    ok: bool
    external_id: str = ""
    url: str = ""
    detail: str = ""
    dry_run: bool = False
    pending: bool = False
    tool_call: dict[str, Any] | None = None
