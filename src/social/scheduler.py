"""Scheduling and the publish loop.

Posting slots come from ``social.posting_times`` in the local timezone. The
scheduler fills the next free slots per platform, never double-booking a time
that already holds a post.
"""

from __future__ import annotations

import time
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Iterable
from zoneinfo import ZoneInfo

from .config import ROOT, SocialConfig
from .models import APPROVED, FAILED, HANDOFF, PUBLISHED, Post, PublishResult, now_iso
from .platforms import NotConfigured, PublishError, Publisher, get_publisher
from .store import Store

UTC = timezone.utc


def tz(cfg: SocialConfig) -> ZoneInfo:
    try:
        return ZoneInfo(cfg.timezone)
    except Exception:
        return ZoneInfo("UTC")


def _parse_slot(value: str) -> tuple[int, int]:
    hour, _, minute = value.partition(":")
    return int(hour), int(minute or 0)


def upcoming_slots(
    cfg: SocialConfig,
    platform: str,
    count: int,
    start: datetime | None = None,
    taken: Iterable[str] = (),
    per_day: int | None = None,
) -> list[datetime]:
    """The next ``count`` free posting times for a platform, as UTC datetimes."""
    zone = tz(cfg)
    now = (start or datetime.now(UTC)).astimezone(zone)
    slots = sorted(_parse_slot(s) for s in cfg.slots_for(platform))
    if not slots:
        slots = [(9, 0)]
    limit_per_day = per_day or len(slots)
    taken_set = set(taken)

    out: list[datetime] = []
    day = now.date()
    for _ in range(90):  # look up to three months ahead
        used_today = 0
        for hour, minute in slots:
            if used_today >= limit_per_day:
                break
            candidate = datetime(day.year, day.month, day.day, hour, minute, tzinfo=zone)
            if candidate <= now:
                continue
            stamp = candidate.astimezone(UTC).replace(microsecond=0).isoformat()
            if stamp in taken_set:
                continue
            out.append(candidate.astimezone(UTC).replace(microsecond=0))
            taken_set.add(stamp)
            used_today += 1
            if len(out) >= count:
                return out
        day += timedelta(days=1)
    return out


def schedule_posts(
    store: Store,
    cfg: SocialConfig,
    posts: list[Post],
    start: datetime | None = None,
    per_day: int | None = None,
) -> list[Post]:
    """Assign each post the next free slot on its platform."""
    by_platform: dict[str, list[Post]] = {}
    for post in posts:
        by_platform.setdefault(post.platform, []).append(post)

    for platform, group in by_platform.items():
        slots = upcoming_slots(
            cfg,
            platform,
            len(group),
            start=start,
            taken=store.scheduled_times(platform),
            per_day=per_day or cfg.posts_per_day,
        )
        for post, when in zip(group, slots):
            post.scheduled_at = when.isoformat()
    return posts


@dataclass
class RunReport:
    attempted: int = 0
    handed_off: int = 0
    published: int = 0
    failed: int = 0
    details: list[str] = None  # type: ignore[assignment]

    def __post_init__(self) -> None:
        if self.details is None:
            self.details = []

    def to_dict(self) -> dict:
        return {
            "attempted": self.attempted,
            "handed_off": self.handed_off,
            "published": self.published,
            "failed": self.failed,
            "details": self.details,
        }


def _media_paths(post: Post) -> list[Path]:
    paths = []
    for asset in post.media:
        p = Path(asset.path)
        paths.append(p if p.is_absolute() else ROOT / p)
    return paths


def publish_post(
    store: Store, cfg: SocialConfig, post: Post, publisher: Publisher | None = None
) -> PublishResult:
    """Deliver a single post and persist the outcome."""
    publisher = publisher or get_publisher(cfg)
    account = store.account(post.account_id) if post.account_id else None
    if account is None:
        matches = store.accounts(platform=post.platform, enabled_only=True)
        account = matches[0] if matches else None

    problems = post.validate()
    if problems:
        post.status = FAILED
        post.error = "; ".join(problems)
        store.save_post(post)
        store.log("validation_failed", post.error, post_id=post.id)
        return PublishResult(ok=False, detail=post.error)

    post.attempts += 1
    try:
        result = publisher.publish(post, account, _media_paths(post))
    except (NotConfigured, PublishError) as exc:
        post.error = str(exc)
        post.status = FAILED if post.attempts >= cfg.max_attempts else APPROVED
        if post.status == APPROVED:
            retry_at = datetime.now(UTC) + timedelta(seconds=cfg.retry_backoff_seconds)
            post.scheduled_at = retry_at.replace(microsecond=0).isoformat()
        store.save_post(post)
        store.log("publish_error", post.error, post_id=post.id, attempts=post.attempts)
        return PublishResult(ok=False, detail=post.error)

    post.error = ""
    post.external_id = result.external_id or post.external_id
    post.external_url = result.url or post.external_url
    if result.pending:
        post.status = HANDOFF
        store.log("handed_off", result.detail, post_id=post.id, tool_call=result.tool_call)
    else:
        post.status = PUBLISHED
        post.published_at = now_iso()
        store.log("published", result.detail, post_id=post.id, url=result.url)
    store.save_post(post)
    return result


def run_once(store: Store, cfg: SocialConfig, limit: int = 25) -> RunReport:
    """Deliver everything that is due right now."""
    publisher = get_publisher(cfg)
    report = RunReport()
    for post in store.due_posts(now_iso(), limit=limit):
        report.attempted += 1
        result = publish_post(store, cfg, post, publisher)
        if not result.ok:
            report.failed += 1
            report.details.append(f"{post.platform}: {result.detail}")
        elif result.pending:
            report.handed_off += 1
            report.details.append(f"{post.platform}: {result.detail}")
        else:
            report.published += 1
            report.details.append(f"{post.platform}: {result.detail}")
    return report


def run_forever(store: Store, cfg: SocialConfig, interval: int = 60, on_report=None) -> None:
    """Poll the queue until interrupted — the worker behind `social worker`."""
    while True:
        report = run_once(store, cfg)
        if on_report and report.attempted:
            on_report(report)
        time.sleep(max(interval, 5))
