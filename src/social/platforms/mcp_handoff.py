"""MCP hand-off publisher — publishing without a single API key.

The app never talks to a social platform directly. When a post comes due it
writes a **job**: the exact MCP tool call that publishes it (by default
``mcp__Buffer__create_post``). Your Claude Code session — which already has
those MCP servers connected and approved — picks the job up, runs the tool, and
acknowledges the result back into the queue.

Routing lives in ``config.yaml → social.mcp`` and on each account
(``settings.channel_id``), so pointing the app at a different MCP server is a
config change, not a code change.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field, asdict
from datetime import datetime
from pathlib import Path
from typing import Any

from ..config import ROOT
from ..models import Account, Post, PublishResult, now_iso
from .base import NotConfigured, Publisher

DEFAULT_MCP = {
    "server": "Buffer",
    "tool": "create_post",
    "posting_type": "addToQueue",   # addToQueue | schedule | share
    "channels": {},                 # platform -> MCP channel id
    "text_arg": "text",
    "channel_arg": "channelIds",
    "schedule_arg": "scheduledAt",
    "media_arg": "media",
}


@dataclass
class ToolCall:
    """One MCP tool invocation, ready for an agent to run."""

    server: str
    tool: str
    arguments: dict[str, Any] = field(default_factory=dict)

    @property
    def qualified_name(self) -> str:
        return f"mcp__{self.server}__{self.tool}"

    def to_dict(self) -> dict[str, Any]:
        return {"name": self.qualified_name, **asdict(self)}

    def as_instruction(self) -> str:
        args = json.dumps(self.arguments, indent=2)
        return f"Call {self.qualified_name} with:\n{args}"


class McpHandoffPublisher(Publisher):
    name = "mcp"

    def __init__(self, config=None, outbox: str | Path | None = None):
        super().__init__(config)
        self.mcp = {**DEFAULT_MCP, **((getattr(config, "mcp", None) or {}) if config else {})}
        self.outbox = Path(outbox) if outbox else ROOT / "data" / "outbox"

    # -- routing ---------------------------------------------------------
    def channel_for(self, post: Post, account: Account | None) -> str:
        channel = self.setting(account, "channel_id") or str(
            (self.mcp.get("channels") or {}).get(post.platform, "")
        )
        if not channel:
            raise NotConfigured(
                f"{post.platform}: no MCP channel mapped. Run `python -m src.main social channels` "
                f"to list them via {self.mcp['server']}, then set social.mcp.channels.{post.platform} "
                "in config.yaml or settings.channel_id on the account."
            )
        return channel

    def build_call(self, post: Post, account: Account | None, media: list[Path]) -> ToolCall:
        """Translate a post into the MCP tool call that publishes it."""
        channel = self.channel_for(post, account)
        posting_type = self.mcp.get("posting_type", "addToQueue")

        arguments: dict[str, Any] = {
            self.mcp["channel_arg"]: [channel],
            self.mcp["text_arg"]: post.full_text,
            "postingType": posting_type,
        }
        if posting_type == "schedule":
            arguments[self.mcp["schedule_arg"]] = _iso_z(post.scheduled_at)
        if media:
            arguments[self.mcp["media_arg"]] = [
                {"path": str(p), "alt": post.media[i].alt if i < len(post.media) else ""}
                for i, p in enumerate(media)
            ]
        if post.title and post.platform in ("youtube", "pinterest"):
            arguments["title"] = post.title
        if post.first_comment:
            arguments["firstComment"] = post.first_comment
        return ToolCall(server=self.mcp["server"], tool=self.mcp["tool"], arguments=arguments)

    # -- delivery ---------------------------------------------------------
    def publish(self, post: Post, account: Account | None, media: list[Path]) -> PublishResult:
        call = self.build_call(post, account, media)
        job = {
            "post_id": post.id,
            "platform": post.platform,
            "account": account.handle if account else "",
            "campaign": post.campaign,
            "scheduled_at": post.scheduled_at,
            "created_at": now_iso(),
            "text": post.full_text,
            "media": [str(m) for m in media],
            "tool_call": call.to_dict(),
            "instruction": call.as_instruction(),
            "ack": (
                f"After the tool returns, record it: "
                f"python -m src.main social ack {post.id} --external-id <id> --url <url>"
            ),
        }
        pending = self.outbox / "pending"
        pending.mkdir(parents=True, exist_ok=True)
        (pending / f"{post.id}.json").write_text(json.dumps(job, indent=2), encoding="utf-8")

        return PublishResult(
            ok=True,
            pending=True,
            detail=f"job ready for {call.qualified_name}",
            tool_call=call.to_dict(),
        )

    # -- acknowledgement ---------------------------------------------------
    def complete(self, post_id: str) -> None:
        """Move a finished job out of the pending folder."""
        pending = self.outbox / "pending" / f"{post_id}.json"
        if not pending.exists():
            return
        done = self.outbox / "done"
        done.mkdir(parents=True, exist_ok=True)
        pending.replace(done / pending.name)

    def pending_jobs(self) -> list[dict[str, Any]]:
        folder = self.outbox / "pending"
        if not folder.exists():
            return []
        jobs = []
        for path in sorted(folder.glob("*.json")):
            try:
                jobs.append(json.loads(path.read_text(encoding="utf-8")))
            except ValueError:
                continue
        return jobs


def _iso_z(value: str) -> str:
    """Normalize a stored timestamp to the UTC ``...Z`` form MCP tools expect."""
    try:
        dt = datetime.fromisoformat(value)
    except ValueError:
        return value
    return dt.astimezone(tz=None).astimezone().isoformat() if dt.tzinfo is None else (
        dt.isoformat().replace("+00:00", "Z")
    )
