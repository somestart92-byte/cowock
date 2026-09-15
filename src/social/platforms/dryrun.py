"""Dry-run publisher — the default, and what every test runs against.

Writes exactly what *would* be sent to disk under ``data/outbox`` so you can
review real payloads before ever connecting an account.
"""

from __future__ import annotations

import json
from pathlib import Path

from ..config import ROOT
from ..models import Account, Post, PublishResult, now_iso
from .base import Publisher


class DryRunPublisher(Publisher):
    name = "dry-run"

    def __init__(self, config=None, outbox: str | Path | None = None):
        super().__init__(config)
        self.outbox = Path(outbox) if outbox else ROOT / "data" / "outbox"

    def configured(self) -> bool:
        return True

    def publish(self, post: Post, account: Account | None, media: list[Path]) -> PublishResult:
        self.outbox.mkdir(parents=True, exist_ok=True)
        payload = {
            "platform": post.platform,
            "account": account.handle if account else "(none)",
            "scheduled_at": post.scheduled_at,
            "sent_at": now_iso(),
            "title": post.title,
            "text": post.full_text,
            "first_comment": post.first_comment,
            "media": [str(m) for m in media],
            "characters": len(post.full_text),
        }
        target = self.outbox / f"{post.scheduled_at[:10]}-{post.platform}-{post.id}.json"
        target.write_text(json.dumps(payload, indent=2), encoding="utf-8")
        return PublishResult(
            ok=True,
            external_id=f"dryrun-{post.id}",
            url=f"file://{target}",
            detail=f"DRY-RUN — payload written to {target.relative_to(ROOT) if target.is_relative_to(ROOT) else target}",
            dry_run=True,
        )
