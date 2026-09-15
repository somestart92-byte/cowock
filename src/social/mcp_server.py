"""cowock-social as an MCP server.

Run it from Claude Code (or any MCP client) and the whole app becomes tools:
write posts, render videos, review the queue, and hand finished jobs to your
publishing MCP server (Buffer & co.) — no platform API keys anywhere.

    claude mcp add cowock-social -- python -m src.social.mcp_server

The publishing bridge is deliberate: ``next_jobs`` hands back the exact tool
call to make (e.g. ``mcp__Buffer__create_post`` with channel ids and text), the
agent runs it with its own approved permissions, then calls ``mark_published``.
"""

from __future__ import annotations

import sys
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

try:  # mcp >= 2
    from mcp.server.mcpserver import MCPServer as _Server
except ModuleNotFoundError:  # pragma: no cover - mcp 1.x
    from mcp.server.fastmcp import FastMCP as _Server  # type: ignore

from src.social.models import APPROVED, DRAFT, HANDOFF
from src.social.platforms import McpHandoffPublisher
from src.social.service import SocialService

server = _Server(
    name="cowock-social",
    version="0.1.0",
    instructions=(
        "Social media automation: generate posts and short videos, keep a "
        "scheduled queue, and publish through the user's own MCP publishing "
        "server. Typical flow: generate_posts or create_video_campaign → "
        "list_queue → approve_posts → next_jobs → run each returned tool call "
        "on the publishing MCP server → mark_published."
    ),
)

_service: SocialService | None = None


def svc() -> SocialService:
    global _service
    if _service is None:
        _service = SocialService()
    return _service


def _post_view(post) -> dict[str, Any]:
    return {
        "id": post.id,
        "platform": post.platform,
        "status": post.status,
        "scheduled_at": post.scheduled_at,
        "text": post.full_text,
        "media": [m.path for m in post.media],
        "campaign": post.campaign,
        "issues": post.validate(),
        "error": post.error,
        "url": post.external_url,
    }


# ------------------------------------------------------------------ content
@server.tool(description="Generate platform-native posts for a topic and queue them as drafts.")
def generate_posts(
    topic: str,
    platforms: list[str] | None = None,
    count: int = 1,
    angle: str = "",
    cta: str = "",
    link: str = "",
    campaign: str = "default",
    approve: bool = False,
) -> dict[str, Any]:
    result = svc().create_posts(
        topic,
        platforms,
        count=count,
        angle=angle,
        cta=cta,
        link=link,
        campaign=campaign,
        approve=approve,
    )
    return {
        "created": len(result.posts),
        "flagged_by_compliance": result.flagged,
        "posts": [_post_view(p) for p in result.posts],
    }


@server.tool(description="Write a short-form video script and render it to an MP4 (vertical by default).")
def generate_video(
    topic: str,
    scenes: int = 6,
    angle: str = "",
    cta: str = "",
    theme: str = "",
    preset: str = "",
    voiceover: str = "",
) -> dict[str, Any]:
    overrides = {
        k: v
        for k, v in {"theme": theme or None, "preset": preset or None, "voiceover": voiceover or None}.items()
        if v
    }
    rendered, script = svc().make_video(topic, scenes=scenes, angle=angle, cta=cta, **overrides)
    return {"video": rendered.to_dict(), "script": script.to_dict()}


@server.tool(description="Render a video AND the matching captions, then schedule them across platforms.")
def create_video_campaign(
    topic: str,
    platforms: list[str] | None = None,
    scenes: int = 6,
    angle: str = "",
    cta: str = "",
    campaign: str = "default",
    theme: str = "",
    approve: bool = False,
) -> dict[str, Any]:
    result = svc().create_video_campaign(
        topic,
        platforms,
        scenes=scenes,
        angle=angle,
        cta=cta,
        campaign=campaign,
        approve=approve,
        **({"theme": theme} if theme else {}),
    )
    return {
        "video": result.video.to_dict() if result.video else None,
        "posts": [_post_view(p) for p in result.posts],
        "flagged_by_compliance": result.flagged,
    }


@server.tool(description="Render a standalone branded graphic (style: slide or quote).")
def generate_image(text: str, style: str = "slide", theme: str = "", size: str = "square") -> dict[str, Any]:
    path = svc().make_image(text, style=style, theme=theme, size=size)
    return {"path": str(path)}


# -------------------------------------------------------------------- queue
@server.tool(description="List queued posts. status: draft, approved, handoff, published, failed, cancelled.")
def list_queue(status: str = "", limit: int = 50) -> dict[str, Any]:
    posts = svc().queue(status=status or None, limit=limit)
    return {"count": len(posts), "posts": [_post_view(p) for p in posts]}


@server.tool(description="Approve draft posts so the scheduler may publish them.")
def approve_posts(post_ids: list[str]) -> dict[str, Any]:
    approved = svc().approve(post_ids)
    return {"approved": [p.id for p in approved], "count": len(approved)}


@server.tool(description="Cancel posts so they are never published.")
def cancel_posts(post_ids: list[str]) -> dict[str, Any]:
    cancelled = svc().cancel(post_ids)
    return {"cancelled": [p.id for p in cancelled]}


@server.tool(description="Edit a queued post's text, hashtags, link or scheduled time.")
def edit_post(
    post_id: str,
    body: str = "",
    title: str = "",
    link: str = "",
    first_comment: str = "",
    hashtags: list[str] | None = None,
    scheduled_at: str = "",
) -> dict[str, Any]:
    post = svc().update_post(
        post_id,
        body=body or None,
        title=title or None,
        link=link or None,
        first_comment=first_comment or None,
        hashtags=hashtags,
        scheduled_at=scheduled_at or None,
    )
    return _post_view(post) if post else {"error": f"no post {post_id}"}


# ---------------------------------------------------------------- publishing
@server.tool(
    description=(
        "Get publishing jobs that are due now. Each job contains the exact MCP tool call to run "
        "on your publishing server (e.g. mcp__Buffer__create_post). Run them, then call "
        "mark_published for each."
    )
)
def next_jobs(limit: int = 10, include_pending: bool = True) -> dict[str, Any]:
    service = svc()
    report = service.run_due(limit=limit)
    jobs = service.pending_jobs() if include_pending else []
    return {
        "report": report.to_dict(),
        "jobs": [
            {
                "post_id": j["post_id"],
                "platform": j["platform"],
                "tool_call": j["tool_call"],
                "text": j["text"],
                "media": j["media"],
                "scheduled_at": j["scheduled_at"],
            }
            for j in jobs
        ],
        "note": "Nothing was published by this tool. Run each tool_call yourself, then mark_published.",
    }


@server.tool(description="Preview the MCP tool call for one post without waiting for its slot.")
def publish_now(post_id: str) -> dict[str, Any]:
    return svc().publish_now(post_id)


@server.tool(description="Record that a post went live (call after the publishing tool call succeeded).")
def mark_published(post_id: str, external_id: str = "", url: str = "") -> dict[str, Any]:
    post = svc().ack(post_id, external_id=external_id, url=url)
    return _post_view(post) if post else {"error": f"no post {post_id}"}


@server.tool(description="Record that publishing a post failed, with the error from the tool call.")
def mark_failed(post_id: str, error: str) -> dict[str, Any]:
    post = svc().fail(post_id, error)
    return _post_view(post) if post else {"error": f"no post {post_id}"}


# ------------------------------------------------------------------ accounts
@server.tool(description="Register a destination account and its publishing-server channel id.")
def add_account(platform: str, handle: str, channel_id: str = "", display_name: str = "") -> dict[str, Any]:
    account = svc().add_account(
        platform, handle, channel_id=channel_id, display_name=display_name
    )
    return {"id": account.id, "platform": account.platform, "handle": account.handle}


@server.tool(description="List registered accounts and their mapped channel ids.")
def list_accounts() -> dict[str, Any]:
    return {
        "accounts": [
            {
                "id": a.id,
                "platform": a.platform,
                "handle": a.handle,
                "enabled": a.enabled,
                "channel_id": a.settings.get("channel_id", ""),
            }
            for a in svc().accounts()
        ]
    }


@server.tool(description="Save performance numbers for a published post so future content can learn from them.")
def record_metrics(
    post_id: str,
    impressions: int = 0,
    likes: int = 0,
    comments: int = 0,
    shares: int = 0,
    clicks: int = 0,
) -> dict[str, Any]:
    svc().record_metrics(
        post_id,
        impressions=impressions,
        likes=likes,
        comments=comments,
        shares=shares,
        clicks=clicks,
    )
    return {"ok": True, "post_id": post_id}


@server.tool(description="Queue health: counts by status, pending MCP jobs, what's next, metric totals.")
def stats() -> dict[str, Any]:
    return svc().stats()


def main() -> None:
    server.run("stdio")


if __name__ == "__main__":
    main()
