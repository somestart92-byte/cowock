"""Command line for the social app: `python -m src.main social <command>`."""

from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

from .config import ROOT, load_config
from .models import STATUSES
from .service import SocialService

BAR = "─" * 72


def _fmt_time(iso: str, zone: str) -> str:
    try:
        return datetime.fromisoformat(iso).astimezone(ZoneInfo(zone)).strftime("%a %d %b %H:%M")
    except Exception:
        return iso


def _print_posts(posts, zone: str) -> None:
    if not posts:
        print("(nothing here yet)")
        return
    for post in posts:
        head = f"{post.status.upper():<9} {post.platform:<10} {_fmt_time(post.scheduled_at, zone)}"
        print(f"\n{head}  [{post.id}]")
        body = post.full_text.strip().splitlines()
        for line in body[:6]:
            print(f"  {line}")
        if len(body) > 6:
            print(f"  … (+{len(body) - 6} lines)")
        if post.media:
            print(f"  media: {', '.join(m.path for m in post.media)}")
        if post.error:
            print(f"  ⚠ {post.error}")


def _service(args) -> SocialService:
    cfg = load_config(getattr(args, "config", None))
    if getattr(args, "live", False):
        cfg.publish_mode = "live"
    return SocialService(cfg)


def _split(value: str | None) -> list[str]:
    return [v.strip() for v in (value or "").split(",") if v.strip()]


# ------------------------------------------------------------------ commands
def cmd_post(args) -> int:
    svc = _service(args)
    result = svc.create_posts(
        args.topic,
        _split(args.platforms) or None,
        count=args.count,
        angle=args.angle,
        cta=args.cta,
        link=args.link,
        campaign=args.campaign,
        keywords=_split(args.keywords),
        approve=args.approve or None,
    )
    print(f"\n{len(result.posts)} post(s) queued for '{args.topic}'")
    if result.flagged:
        print(f"⚠ {len(result.flagged)} flagged by the compliance review — left as drafts.")
    _print_posts(result.posts, svc.config.timezone)
    print(f"\n{BAR}\nApprove with:  python -m src.main social approve --all")
    return 0


def cmd_video(args) -> int:
    svc = _service(args)
    overrides = {
        k: v
        for k, v in {
            "theme": args.theme,
            "preset": args.preset,
            "voiceover": args.voiceover,
            "seconds_per_scene": args.seconds,
            "music": args.music,
        }.items()
        if v
    }
    if args.post:
        result = svc.create_video_campaign(
            args.topic,
            _split(args.platforms) or None,
            scenes=args.scenes,
            angle=args.angle,
            cta=args.cta,
            campaign=args.campaign,
            approve=args.approve or None,
            **overrides,
        )
        video = result.video
        print(f"\n🎬 {video.path}  ({video.duration:.1f}s, {video.scenes} scenes, {video.width}x{video.height})")
        _print_posts(result.posts, svc.config.timezone)
    else:
        video, script = svc.make_video(
            args.topic, scenes=args.scenes, angle=args.angle, cta=args.cta, **overrides
        )
        print(f"\n🎬 {video.path}")
        print(f"   {video.duration:.1f}s · {video.scenes} scenes · {video.width}x{video.height}"
              f" · voiceover: {'yes' if video.voiceover else 'no'}")
        print(f"\nScript — {script.title}")
        for i, scene in enumerate(script.scenes, 1):
            print(f"  {i}. {scene.text}")
            if scene.voiceover:
                print(f"     🎙 {scene.voiceover}")
    return 0


def cmd_image(args) -> int:
    svc = _service(args)
    path = svc.make_image(args.text, style=args.style, theme=args.theme or "", size=args.size)
    print(f"🖼  {path}")
    return 0


def cmd_queue(args) -> int:
    svc = _service(args)
    posts = svc.queue(status=args.status or None, limit=args.limit)
    print(f"{BAR}\nQueue — {len(posts)} post(s){' · ' + args.status if args.status else ''}\n{BAR}")
    _print_posts(posts, svc.config.timezone)
    return 0


def cmd_approve(args) -> int:
    svc = _service(args)
    ids = args.post_ids
    if args.all:
        ids = [p.id for p in svc.queue(status="draft", limit=500)]
    approved = svc.approve(ids)
    print(f"✅ approved {len(approved)} post(s)")
    for post in approved:
        print(f"   {post.platform:<10} {_fmt_time(post.scheduled_at, svc.config.timezone)}  [{post.id}]")
    skipped = len(ids) - len(approved)
    if skipped > 0:
        print(f"⚠ {skipped} skipped (already approved, or failing validation — see `social queue`)")
    return 0


def cmd_cancel(args) -> int:
    svc = _service(args)
    print(f"🚫 cancelled {len(svc.cancel(args.post_ids))} post(s)")
    return 0


def cmd_run(args) -> int:
    svc = _service(args)
    report = svc.run_due(limit=args.limit)
    print(f"attempted {report.attempted} · handed off {report.handed_off} · "
          f"published {report.published} · failed {report.failed}")
    for detail in report.details:
        print(f"  • {detail}")
    if report.handed_off:
        print("\nRun the pending MCP tool calls:  python -m src.main social jobs")
    return 0


def cmd_worker(args) -> int:
    from .scheduler import run_forever

    svc = _service(args)
    print(f"worker started · mode={svc.config.publish_mode} · every {args.interval}s · Ctrl-C to stop")
    try:
        run_forever(
            svc.store,
            svc.config,
            interval=args.interval,
            on_report=lambda r: print(f"[{datetime.now():%H:%M:%S}] {r.to_dict()}"),
        )
    except KeyboardInterrupt:
        print("\nworker stopped")
    return 0


def cmd_jobs(args) -> int:
    svc = _service(args)
    jobs = svc.pending_jobs()
    if not jobs:
        print("No pending jobs. Run `python -m src.main social run --live` when posts are due.")
        return 0
    print(f"{BAR}\n{len(jobs)} job(s) waiting for your MCP publishing tools\n{BAR}")
    for job in jobs:
        due = _fmt_time(job["scheduled_at"], svc.config.timezone)
        print(f"\n▸ {job['platform']}  [{job['post_id']}]  due {due}")
        if args.json:
            print(json.dumps(job["tool_call"], indent=2))
        else:
            print(job["instruction"])
            if job["media"]:
                print(f"  media: {', '.join(job['media'])}")
            print(f"  then: {job['ack']}")
    return 0


def cmd_ack(args) -> int:
    svc = _service(args)
    post = svc.ack(args.post_id, external_id=args.external_id, url=args.url)
    print(f"✅ {args.post_id} marked published" if post else f"no post {args.post_id}")
    return 0 if post else 1


def cmd_fail(args) -> int:
    svc = _service(args)
    post = svc.fail(args.post_id, args.error)
    print(f"❌ {args.post_id} marked failed" if post else f"no post {args.post_id}")
    return 0 if post else 1


def cmd_accounts(args) -> int:
    svc = _service(args)
    if args.add:
        account = svc.add_account(args.add, args.handle or args.add, channel_id=args.channel_id or "")
        print(f"added {account.platform} {account.handle} [{account.id}]")
        return 0
    accounts = svc.accounts()
    if not accounts:
        print("No accounts yet. Add one:\n"
              "  python -m src.main social accounts --add x --handle @you --channel-id <mcp channel id>")
        return 0
    for a in accounts:
        state = "on " if a.enabled else "off"
        print(f"{state} {a.platform:<10} {a.handle:<22} channel={a.settings.get('channel_id', '—')}  [{a.id}]")
    return 0


def cmd_channels(args) -> int:
    svc = _service(args)
    server = svc.config.mcp.get("server", "Buffer")
    print(
        f"Channel ids come from your publishing MCP server, not from this app.\n\n"
        f"In Claude Code, ask:\n"
        f"  \"list my {server} channels\"   (runs mcp__{server}__list_channels)\n\n"
        f"Then map them:\n"
        f"  python -m src.main social accounts --add instagram --handle @you --channel-id <id>\n"
        f"or in config.yaml:\n"
        f"  social:\n    mcp:\n      channels:\n        instagram: <id>\n"
    )
    return 0


def cmd_stats(args) -> int:
    svc = _service(args)
    stats = svc.stats()
    print(f"{BAR}")
    print(f"mode: {stats['publish_mode']}   MCP server: {stats['mcp_server']}   "
          f"copy: {'templates (no API key)' if stats['dry_run_llm'] else 'live model'}")
    print(f"posts: {stats['total']}  " + "  ".join(f"{k}={v}" for k, v in stats["counts"].items()))
    print(f"pending MCP jobs: {stats['pending_jobs']}")
    if stats["next"]:
        print("\nnext up:")
        for item in stats["next"]:
            print(f"  {item['status']:<9} {item['platform']:<10} {_fmt_time(item['at'], svc.config.timezone)}")
    if stats["metrics"]:
        print("\nmetrics:")
        for row in stats["metrics"]:
            print(f"  {row['platform']:<10} impressions={row['impressions']} likes={row['likes']}")
    print(BAR)
    return 0


def cmd_serve(args) -> int:
    from .web.app import serve

    serve(host=args.host, port=args.port, config_path=getattr(args, "config", None))
    return 0


def cmd_mcp(args) -> int:
    from .mcp_server import main as mcp_main

    mcp_main()
    return 0


# -------------------------------------------------------------------- parser
def build_parser(sub) -> None:
    """Attach the `social` command tree to an existing subparsers object."""
    p = sub.add_parser("social", help="generate, schedule and publish social content")
    p.add_argument("--config", default=None, help="path to config.yaml")
    p.add_argument("--live", action="store_true", help="use MCP hand-off instead of dry-run preview")
    cmds = p.add_subparsers(dest="social_command", required=True)

    post = cmds.add_parser("post", help="generate posts for a topic")
    post.add_argument("topic")
    post.add_argument("--platforms", help="comma separated (default: config)")
    post.add_argument("--count", type=int, default=1, help="variants per platform")
    post.add_argument("--angle", default="")
    post.add_argument("--cta", default="")
    post.add_argument("--link", default="")
    post.add_argument("--keywords", default="")
    post.add_argument("--campaign", default="default")
    post.add_argument("--approve", action="store_true", help="queue as approved, ready to publish")
    post.set_defaults(func=cmd_post)

    video = cmds.add_parser("video", help="write a script and render a short video")
    video.add_argument("topic")
    video.add_argument("--scenes", type=int, default=6)
    video.add_argument("--angle", default="")
    video.add_argument("--cta", default="")
    video.add_argument("--theme", default="", help="midnight | ink | sand | berry | slate")
    video.add_argument("--preset", default="", help="vertical | square | landscape")
    video.add_argument("--voiceover", default="", help="none | espeak | elevenlabs")
    video.add_argument("--seconds", type=float, default=None, help="seconds per scene")
    video.add_argument("--music", default="", help="path to a background audio file")
    video.add_argument("--post", action="store_true", help="also write captions and queue them")
    video.add_argument("--platforms", help="comma separated (with --post)")
    video.add_argument("--campaign", default="default")
    video.add_argument("--approve", action="store_true")
    video.set_defaults(func=cmd_video)

    image = cmds.add_parser("image", help="render a branded graphic")
    image.add_argument("text")
    image.add_argument("--style", default="slide", choices=["slide", "quote"])
    image.add_argument("--theme", default="")
    image.add_argument("--size", default="square", choices=["vertical", "square", "landscape", "pin"])
    image.set_defaults(func=cmd_image)

    queue = cmds.add_parser("queue", help="show the queue")
    queue.add_argument("--status", default="", choices=["", *STATUSES])
    queue.add_argument("--limit", type=int, default=50)
    queue.set_defaults(func=cmd_queue)

    approve = cmds.add_parser("approve", help="approve drafts")
    approve.add_argument("post_ids", nargs="*")
    approve.add_argument("--all", action="store_true", help="approve every draft")
    approve.set_defaults(func=cmd_approve)

    cancel = cmds.add_parser("cancel", help="cancel posts")
    cancel.add_argument("post_ids", nargs="+")
    cancel.set_defaults(func=cmd_cancel)

    run = cmds.add_parser("run", help="process everything that is due now")
    run.add_argument("--limit", type=int, default=25)
    run.set_defaults(func=cmd_run)

    worker = cmds.add_parser("worker", help="keep processing the queue on a loop")
    worker.add_argument("--interval", type=int, default=60)
    worker.set_defaults(func=cmd_worker)

    jobs = cmds.add_parser("jobs", help="show MCP tool calls waiting to be run")
    jobs.add_argument("--json", action="store_true")
    jobs.set_defaults(func=cmd_jobs)

    ack = cmds.add_parser("ack", help="mark a post published after its MCP call succeeded")
    ack.add_argument("post_id")
    ack.add_argument("--external-id", default="", dest="external_id")
    ack.add_argument("--url", default="")
    ack.set_defaults(func=cmd_ack)

    fail = cmds.add_parser("fail", help="mark a post failed")
    fail.add_argument("post_id")
    fail.add_argument("--error", required=True)
    fail.set_defaults(func=cmd_fail)

    accounts = cmds.add_parser("accounts", help="list or add destination accounts")
    accounts.add_argument("--add", default="", help="platform to add")
    accounts.add_argument("--handle", default="")
    accounts.add_argument("--channel-id", default="", dest="channel_id")
    accounts.set_defaults(func=cmd_accounts)

    channels = cmds.add_parser("channels", help="how to find your MCP channel ids")
    channels.set_defaults(func=cmd_channels)

    stats = cmds.add_parser("stats", help="queue health and totals")
    stats.set_defaults(func=cmd_stats)

    serve = cmds.add_parser("serve", help="run the web dashboard")
    serve.add_argument("--host", default="127.0.0.1")
    serve.add_argument("--port", type=int, default=8000)
    serve.set_defaults(func=cmd_serve)

    mcp = cmds.add_parser("mcp", help="run the MCP server on stdio")
    mcp.set_defaults(func=cmd_mcp)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="cowock-social")
    sub = parser.add_subparsers(dest="command", required=True)
    build_parser(sub)
    args = parser.parse_args(argv or sys.argv[1:])
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())
