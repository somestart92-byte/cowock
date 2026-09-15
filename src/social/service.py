"""The application layer: one object the CLI, the web UI and the MCP server share."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any, Iterable

from src.agent import compliance
from src.agent.llm import LLM

from .config import ROOT, SocialConfig, load_config
from .generate import ContentBrief, VideoScript, generate_posts, generate_video_script
from .models import (
    APPROVED,
    CANCELLED,
    DRAFT,
    FAILED,
    HANDOFF,
    PUBLISHED,
    Account,
    MediaAsset,
    Post,
    now_iso,
)
from .platforms import McpHandoffPublisher, get_publisher
from .render.image import render_quote_card, render_slide
from .render.video import RenderedVideo, VideoSpec, render_video
from .scheduler import RunReport, publish_post, run_once, schedule_posts
from .store import Store

VIDEO_PLATFORMS = ("tiktok", "youtube", "instagram", "facebook")


@dataclass
class CampaignResult:
    posts: list[Post]
    video: RenderedVideo | None = None
    script: VideoScript | None = None
    flagged: list[str] = None  # type: ignore[assignment]

    def __post_init__(self) -> None:
        if self.flagged is None:
            self.flagged = []

    def to_dict(self) -> dict[str, Any]:
        return {
            "posts": [p.to_dict() for p in self.posts],
            "video": self.video.to_dict() if self.video else None,
            "script": self.script.to_dict() if self.script else None,
            "flagged": self.flagged,
        }


class SocialService:
    def __init__(self, config: SocialConfig | None = None, store: Store | None = None):
        self.config = config or load_config()
        self.store = store or Store(self.config.resolve(self.config.db_path))
        self._llm: LLM | None = None

    # -- infrastructure --------------------------------------------------
    @property
    def llm(self) -> LLM:
        if self._llm is None:
            self._llm = LLM(
                model=self.config.llm.get("model", "claude-sonnet-5"),
                max_tokens=self.config.llm.get("max_tokens", 4000),
                temperature=self.config.llm.get("temperature", 0.8),
            )
        return self._llm

    @property
    def media_dir(self) -> Path:
        path = self.config.resolve(self.config.media_dir)
        path.mkdir(parents=True, exist_ok=True)
        return path

    def close(self) -> None:
        self.store.close()

    # -- accounts ---------------------------------------------------------
    def add_account(self, platform: str, handle: str, **settings: Any) -> Account:
        account = Account(
            platform=platform,
            handle=handle,
            display_name=str(settings.pop("display_name", "") or handle),
            settings=settings,
        )
        self.store.save_account(account)
        self.store.log("account_added", f"{platform} {handle}")
        return account

    def accounts(self, platform: str | None = None) -> list[Account]:
        return self.store.accounts(platform=platform)

    def _account_for(self, platform: str) -> Account | None:
        matches = self.store.accounts(platform=platform, enabled_only=True)
        return matches[0] if matches else None

    # -- content ----------------------------------------------------------
    def create_posts(
        self,
        topic: str,
        platforms: list[str] | None = None,
        *,
        count: int = 1,
        angle: str = "",
        cta: str = "",
        link: str = "",
        campaign: str = "default",
        keywords: list[str] | None = None,
        media: list[MediaAsset] | None = None,
        start: datetime | None = None,
        approve: bool | None = None,
    ) -> CampaignResult:
        """Generate, screen, schedule and store a batch of posts."""
        brief = ContentBrief(
            topic=topic,
            platforms=platforms or self.config.default_platforms,
            angle=angle,
            cta=cta,
            link=link,
            campaign=campaign,
            count=count,
            keywords=keywords or [],
            audience=str(self.config.brand.get("audience", "")),
        )
        posts = generate_posts(brief, self.config, self.llm)
        flagged = self._screen(posts)

        for post in posts:
            if media:
                post.media = list(media)
            post.account_id = getattr(self._account_for(post.platform), "id", None)

        schedule_posts(self.store, self.config, posts, start=start)

        auto = self.config.auto_approve if approve is None else approve
        for post in posts:
            problems = post.validate()
            if problems:
                post.meta["validation"] = problems
            ok = not problems and post.id not in flagged
            post.status = APPROVED if (auto and ok) else DRAFT
        self.store.save_posts(posts)
        self.store.log(
            "posts_created",
            f"{len(posts)} post(s) for '{topic}'",
            campaign=campaign,
            flagged=len(flagged),
        )
        return CampaignResult(posts=posts, flagged=[p.id for p in posts if p.id in flagged])

    def _screen(self, posts: list[Post]) -> set[str]:
        """Run the halal/honesty reviewer over generated copy."""
        flagged: set[str] = set()
        for post in posts:
            verdict = compliance.review(post.full_text, self.config.rules, self.llm)
            post.meta["compliance"] = verdict.to_dict()
            if not verdict.ok:
                flagged.add(post.id)
                self.store.log(
                    "compliance_flag",
                    "; ".join(verdict.issues) or verdict.notes,
                    post_id=post.id,
                )
        return flagged

    # -- video -------------------------------------------------------------
    def write_script(self, topic: str, scenes: int = 6, angle: str = "", cta: str = "") -> VideoScript:
        return generate_video_script(topic, self.config, self.llm, scenes=scenes, angle=angle, cta=cta)

    def video_spec(self, **overrides: Any) -> VideoSpec:
        spec = VideoSpec.from_config(self.config.video, **overrides)
        if not spec.footer:
            handle = next((a.handle for a in self.store.accounts(enabled_only=True)), "")
            spec.footer = handle
        if not spec.kicker:
            spec.kicker = str(self.config.brand.get("name", ""))
        return spec

    def make_video(
        self,
        topic: str,
        *,
        script: VideoScript | None = None,
        scenes: int = 6,
        angle: str = "",
        cta: str = "",
        slug: str = "",
        **spec_overrides: Any,
    ) -> tuple[RenderedVideo, VideoScript]:
        """Write (or take) a script and render it to an MP4 under ``data/media``."""
        script = script or self.write_script(topic, scenes=scenes, angle=angle, cta=cta)
        stem = slug or _slug(script.title or topic)
        out = self.media_dir / f"{now_iso()[:10]}-{stem}.mp4"
        rendered = render_video(script, out, self.video_spec(**spec_overrides))
        self.store.log(
            "video_rendered",
            f"{rendered.path.name} ({rendered.duration:.1f}s, {rendered.scenes} scenes)",
            path=str(rendered.path),
        )
        return rendered, script

    def make_image(
        self, text: str, *, style: str = "slide", theme: str = "", size: str = "square", footer: str = ""
    ) -> Path:
        """Render a standalone graphic for a feed post."""
        theme = theme or str(self.config.video.get("theme", "midnight"))
        if style == "quote":
            img = render_quote_card(text, theme=theme, size=size, footer=footer)
        else:
            img = render_slide(
                text,
                theme=theme,
                size=size,
                footer=footer,
                kicker=str(self.config.brand.get("name", "")),
            )
        out = self.media_dir / f"{now_iso()[:10]}-{_slug(text)[:40]}.png"
        img.save(out, "PNG")
        return out

    def create_video_campaign(
        self,
        topic: str,
        platforms: list[str] | None = None,
        *,
        scenes: int = 6,
        angle: str = "",
        cta: str = "",
        campaign: str = "default",
        approve: bool | None = None,
        **spec_overrides: Any,
    ) -> CampaignResult:
        """One call: script → video → captions per platform → scheduled queue."""
        platforms = platforms or [p for p in (self.config.default_platforms) if p in VIDEO_PLATFORMS] or [
            "tiktok",
            "instagram",
        ]
        rendered, script = self.make_video(
            topic, scenes=scenes, angle=angle, cta=cta, **spec_overrides
        )
        asset = MediaAsset(
            path=str(rendered.path.relative_to(ROOT) if rendered.path.is_relative_to(ROOT) else rendered.path),
            kind="video",
            alt=script.hook,
        )
        result = self.create_posts(
            topic,
            platforms,
            angle=angle,
            cta=cta,
            campaign=campaign,
            media=[asset],
            approve=approve,
        )
        for post in result.posts:
            post.title = post.title or script.title
            post.meta["video"] = rendered.to_dict()
            post.meta["script"] = script.to_dict()
        self.store.save_posts(result.posts)
        result.video, result.script = rendered, script
        return result

    # -- queue operations ---------------------------------------------------
    def queue(self, status: str | list[str] | None = None, limit: int = 100) -> list[Post]:
        return self.store.posts(status=status, limit=limit)

    def approve(self, post_ids: Iterable[str]) -> list[Post]:
        changed = []
        for pid in post_ids:
            post = self.store.post(pid)
            if not post or post.status not in (DRAFT, FAILED):
                continue
            problems = post.validate()
            if problems:
                post.error = "; ".join(problems)
                self.store.save_post(post)
                continue
            post.status, post.error = APPROVED, ""
            self.store.save_post(post)
            self.store.log("approved", f"{post.platform} post approved", post_id=post.id)
            changed.append(post)
        return changed

    def cancel(self, post_ids: Iterable[str]) -> list[Post]:
        changed = []
        for pid in post_ids:
            post = self.store.post(pid)
            if not post:
                continue
            post.status = CANCELLED
            self.store.save_post(post)
            self.store.log("cancelled", f"{post.platform} post cancelled", post_id=post.id)
            changed.append(post)
        return changed

    def reschedule(self, post_id: str, when: str) -> Post | None:
        post = self.store.post(post_id)
        if not post:
            return None
        post.scheduled_at = when
        self.store.save_post(post)
        self.store.log("rescheduled", f"moved to {when}", post_id=post.id)
        return post

    def update_post(self, post_id: str, **fields: Any) -> Post | None:
        post = self.store.post(post_id)
        if not post:
            return None
        for key in ("body", "title", "link", "first_comment", "scheduled_at"):
            if key in fields and fields[key] is not None:
                setattr(post, key, fields[key])
        if fields.get("hashtags") is not None:
            tags = fields["hashtags"]
            post.hashtags = tags if isinstance(tags, list) else [
                t.strip().lstrip("#") for t in str(tags).split() if t.strip()
            ]
        self.store.save_post(post)
        return post

    # -- delivery ------------------------------------------------------------
    def run_due(self, limit: int = 25) -> RunReport:
        return run_once(self.store, self.config, limit=limit)

    def publish_now(self, post_id: str) -> dict[str, Any]:
        post = self.store.post(post_id)
        if not post:
            return {"ok": False, "detail": f"no post {post_id}"}
        if post.status == DRAFT:
            post.status = APPROVED
        result = publish_post(self.store, self.config, post, get_publisher(self.config))
        return {
            "ok": result.ok,
            "pending": result.pending,
            "detail": result.detail,
            "tool_call": result.tool_call,
        }

    def pending_jobs(self) -> list[dict[str, Any]]:
        """MCP jobs waiting for an agent to run them."""
        return McpHandoffPublisher(self.config).pending_jobs()

    def ack(self, post_id: str, external_id: str = "", url: str = "") -> Post | None:
        """Record that the MCP tool call succeeded."""
        post = self.store.post(post_id)
        if not post:
            return None
        post.status = PUBLISHED
        post.published_at = now_iso()
        post.external_id = external_id or post.external_id
        post.external_url = url or post.external_url
        post.error = ""
        self.store.save_post(post)
        McpHandoffPublisher(self.config).complete(post_id)
        self.store.log("published", f"acked via MCP: {external_id or '(no id)'}", post_id=post_id, url=url)
        return post

    def fail(self, post_id: str, error: str) -> Post | None:
        post = self.store.post(post_id)
        if not post:
            return None
        post.status = FAILED
        post.error = error
        self.store.save_post(post)
        self.store.log("publish_failed", error, post_id=post_id)
        return post

    # -- reporting -------------------------------------------------------------
    def stats(self) -> dict[str, Any]:
        counts = self.store.counts_by_status()
        upcoming = self.store.posts(status=[APPROVED, DRAFT], limit=5)
        return {
            "publish_mode": self.config.publish_mode,
            "mcp_server": self.config.mcp.get("server"),
            "dry_run_llm": self.llm.dry_run,
            "counts": counts,
            "total": sum(counts.values()),
            "pending_jobs": len(self.pending_jobs()),
            "next": [
                {"id": p.id, "platform": p.platform, "at": p.scheduled_at, "status": p.status}
                for p in upcoming
            ],
            "metrics": self.store.metrics_summary(),
        }

    def record_metrics(self, post_id: str, **stats: int) -> None:
        post = self.store.post(post_id)
        if post:
            self.store.record_metrics(post_id, post.platform, **stats)


def _slug(text: str) -> str:
    keep = [c.lower() if c.isalnum() else "-" for c in text.strip()]
    slug = "".join(keep)
    while "--" in slug:
        slug = slug.replace("--", "-")
    return slug.strip("-")[:60] or "post"
