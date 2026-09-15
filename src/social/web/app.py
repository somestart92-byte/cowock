"""FastAPI dashboard: compose, review, approve, and hand jobs to MCP.

Server-rendered on purpose — no build step, no JS bundle, works over SSH port
forwarding. Start it with ``python -m src.main social serve``.
"""

from __future__ import annotations

from datetime import datetime
from pathlib import Path
from typing import Any
from zoneinfo import ZoneInfo

from fastapi import FastAPI, Form, Request
from fastapi.responses import FileResponse, HTMLResponse, JSONResponse, RedirectResponse
from fastapi.templating import Jinja2Templates

from ..config import ROOT, SocialConfig, load_config
from ..models import STATUSES
from ..service import SocialService

TEMPLATES = Jinja2Templates(directory=str(Path(__file__).parent / "templates"))


def _split(value: str | None) -> list[str]:
    return [v.strip() for v in (value or "").replace(",", " ").split() if v.strip()]


def create_app(config: SocialConfig | None = None) -> FastAPI:
    cfg = config or load_config()
    app = FastAPI(title="cowock social", docs_url="/api/docs")
    service = SocialService(cfg)

    def local(iso: str) -> str:
        try:
            return datetime.fromisoformat(iso).astimezone(ZoneInfo(cfg.timezone)).strftime(
                "%a %d %b · %H:%M"
            )
        except Exception:
            return iso

    TEMPLATES.env.filters["local"] = local

    def page(request: Request, name: str, **context: Any) -> HTMLResponse:
        base = {
            "request": request,
            "config": cfg,
            "stats": service.stats(),
            "statuses": STATUSES,
            "nav": name,
        }
        base.update(context)
        return TEMPLATES.TemplateResponse(request, name, base)

    # -- pages ------------------------------------------------------------
    @app.get("/", response_class=HTMLResponse)
    def index(request: Request, status: str = ""):
        posts = service.queue(status=status or None, limit=200)
        return page(request, "queue.html", posts=posts, status=status)

    @app.get("/compose", response_class=HTMLResponse)
    def compose_form(request: Request):
        return page(request, "compose.html", result=None)

    @app.post("/compose", response_class=HTMLResponse)
    def compose(
        request: Request,
        topic: str = Form(...),
        platforms: str = Form(""),
        count: int = Form(1),
        angle: str = Form(""),
        cta: str = Form(""),
        link: str = Form(""),
        campaign: str = Form("default"),
        approve: str = Form(""),
    ):
        result = service.create_posts(
            topic,
            _split(platforms) or None,
            count=count,
            angle=angle,
            cta=cta,
            link=link,
            campaign=campaign,
            approve=bool(approve),
        )
        return page(request, "compose.html", result=result)

    @app.get("/studio", response_class=HTMLResponse)
    def studio_form(request: Request):
        return page(request, "studio.html", result=None)

    @app.post("/studio", response_class=HTMLResponse)
    def studio(
        request: Request,
        topic: str = Form(...),
        scenes: int = Form(6),
        angle: str = Form(""),
        cta: str = Form(""),
        theme: str = Form(""),
        preset: str = Form(""),
        voiceover: str = Form(""),
        platforms: str = Form(""),
        queue_posts: str = Form(""),
        approve: str = Form(""),
    ):
        overrides = {k: v for k, v in
                     {"theme": theme, "preset": preset, "voiceover": voiceover}.items() if v}
        if queue_posts:
            result = service.create_video_campaign(
                topic,
                _split(platforms) or None,
                scenes=scenes,
                angle=angle,
                cta=cta,
                approve=bool(approve),
                **overrides,
            )
            return page(request, "studio.html", result=result)
        video, script = service.make_video(topic, scenes=scenes, angle=angle, cta=cta, **overrides)
        from ..service import CampaignResult

        return page(request, "studio.html", result=CampaignResult(posts=[], video=video, script=script))

    @app.get("/jobs", response_class=HTMLResponse)
    def jobs(request: Request):
        return page(request, "jobs.html", jobs=service.pending_jobs())

    @app.get("/accounts", response_class=HTMLResponse)
    def accounts(request: Request):
        return page(request, "accounts.html", accounts=service.accounts())

    @app.get("/post/{post_id}", response_class=HTMLResponse)
    def post_detail(request: Request, post_id: str):
        post = service.store.post(post_id)
        if not post:
            return RedirectResponse("/", status_code=303)
        return page(request, "post.html", post=post, events=service.store.events(post_id=post_id))

    @app.get("/events", response_class=HTMLResponse)
    def events(request: Request):
        return page(request, "events.html", events=service.store.events(limit=200))

    # -- actions -----------------------------------------------------------
    @app.post("/post/{post_id}/edit")
    def edit(
        post_id: str,
        body: str = Form(""),
        hashtags: str = Form(""),
        link: str = Form(""),
        first_comment: str = Form(""),
        scheduled_at: str = Form(""),
    ):
        when = scheduled_at
        if when:
            try:
                when = (
                    datetime.fromisoformat(when)
                    .replace(tzinfo=ZoneInfo(cfg.timezone))
                    .astimezone(ZoneInfo("UTC"))
                    .replace(microsecond=0)
                    .isoformat()
                )
            except ValueError:
                when = ""
        service.update_post(
            post_id,
            body=body,
            hashtags=_split(hashtags),
            link=link,
            first_comment=first_comment,
            scheduled_at=when or None,
        )
        return RedirectResponse(f"/post/{post_id}", status_code=303)

    @app.post("/post/{post_id}/approve")
    def approve_one(post_id: str):
        service.approve([post_id])
        return RedirectResponse("/", status_code=303)

    @app.post("/post/{post_id}/cancel")
    def cancel_one(post_id: str):
        service.cancel([post_id])
        return RedirectResponse("/", status_code=303)

    @app.post("/post/{post_id}/publish")
    def publish_one(post_id: str):
        service.publish_now(post_id)
        return RedirectResponse("/jobs" if cfg.live else "/", status_code=303)

    @app.post("/post/{post_id}/ack")
    def ack_one(post_id: str, external_id: str = Form(""), url: str = Form("")):
        service.ack(post_id, external_id=external_id, url=url)
        return RedirectResponse("/jobs", status_code=303)

    @app.post("/approve-all")
    def approve_all():
        service.approve([p.id for p in service.queue(status="draft", limit=500)])
        return RedirectResponse("/", status_code=303)

    @app.post("/run")
    def run_due():
        service.run_due()
        return RedirectResponse("/jobs" if cfg.live else "/", status_code=303)

    @app.post("/accounts/add")
    def add_account(
        platform: str = Form(...), handle: str = Form(...), channel_id: str = Form("")
    ):
        service.add_account(platform, handle, channel_id=channel_id)
        return RedirectResponse("/accounts", status_code=303)

    # -- media + json ------------------------------------------------------
    @app.get("/media/{filename:path}")
    def media(filename: str):
        path = (service.media_dir / filename).resolve()
        if not path.is_file() or not path.is_relative_to(service.media_dir.resolve()):
            return JSONResponse({"error": "not found"}, status_code=404)
        return FileResponse(path)

    @app.get("/api/queue")
    def api_queue(status: str = ""):
        return {"posts": [p.to_dict() for p in service.queue(status=status or None, limit=200)]}

    @app.get("/api/stats")
    def api_stats():
        return service.stats()

    @app.get("/api/jobs")
    def api_jobs():
        return {"jobs": service.pending_jobs()}

    return app


def serve(host: str = "127.0.0.1", port: int = 8000, config_path: str | None = None) -> None:
    import uvicorn

    cfg = load_config(config_path)
    print(f"cowock social dashboard → http://{host}:{port}  (mode: {cfg.publish_mode})")
    uvicorn.run(create_app(cfg), host=host, port=port, log_level="info")
