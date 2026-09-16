"""cowock CLI entrypoint.

Usage:
    python -m src.main run                       # generate a product + marketing kit
    python -m src.main run --config path/to/config.yaml
    python -m src.main email build --kind welcome    # write an email campaign
    python -m src.main email send --campaign <slug>  # rehearse into the outbox
    python -m src.main subscribers add you@example.com
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

# Allow running both as `python -m src.main` and `python src/main.py`.
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from src.agent import analytics, email_pipeline, market_research, pipeline
from src.agent.config import load_config
from src.agent.llm import LLM


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="cowock", description="Halal digital-products agent")
    sub = parser.add_subparsers(dest="command", required=True)

    run_p = sub.add_parser("run", help="generate a product + marketing kit")
    run_p.add_argument("--config", default=None, help="path to config.yaml")

    res_p = sub.add_parser("research", help="run market research only")
    res_p.add_argument("--config", default=None, help="path to config.yaml")

    an_p = sub.add_parser("analytics", help="analyze post performance from a metrics JSON")
    an_p.add_argument("--metrics", required=True, help="path to Buffer metrics JSON")
    an_p.add_argument("--config", default=None, help="path to config.yaml")

    email_p = sub.add_parser("email", help="build and send email campaigns")
    email_sub = email_p.add_subparsers(dest="email_command", required=True)

    eb = email_sub.add_parser("build", help="write an email campaign (sends nothing)")
    eb.add_argument("--kind", default="welcome",
                    choices=["welcome", "launch", "nurture", "broadcast"])
    eb.add_argument("--product", default=None,
                    help="product run dir (default: the most recent one)")
    eb.add_argument("--count", type=int, default=None, help="how many emails")
    eb.add_argument("--notes", default="", help="extra context for the copywriter")
    eb.add_argument("--tag", default="", help="only mail subscribers with this tag")
    eb.add_argument("--url", default="", help="product URL the CTA points to")
    eb.add_argument("--config", default=None)

    es = email_sub.add_parser("send", help="send a campaign (outbox rehearsal by default)")
    es.add_argument("--campaign", required=True, help="campaign slug (or part of it)")
    es.add_argument("--live", action="store_true",
                    help="really send over SMTP — needs an approved campaign")
    es.add_argument("--index", type=int, default=None, help="which email in the sequence (0-based)")
    es.add_argument("--drip", action="store_true",
                    help="send each subscriber whichever sequence emails are due")
    es.add_argument("--tag", default="", help="override the audience tag")
    es.add_argument("--limit", type=int, default=None, help="stop after N sends")
    es.add_argument("--backend", default="", choices=["", "outbox", "console", "smtp"])
    es.add_argument("--test-to", default="", help="send only to this address, as a test")
    es.add_argument("--config", default=None)

    el = email_sub.add_parser("list", help="list built campaigns")
    el.add_argument("--config", default=None)

    ei = email_sub.add_parser("inbox", help="read replies and stop chasing people who answered")
    ei.add_argument("--days", type=int, default=30, help="how far back to look")
    ei.add_argument("--config", default=None)

    ed = email_sub.add_parser("dashboard", help="write an HTML inbox you open in a browser")
    ed.add_argument("--open", action="store_true", help="print the file:// link")
    ed.add_argument("--name", default="Cold outreach", help="campaign name for the heading")
    ed.add_argument("--config", default=None)

    ep = email_sub.add_parser("preview", help="print a campaign as Markdown")
    ep.add_argument("--campaign", required=True)
    ep.add_argument("--config", default=None)

    subs_p = sub.add_parser("subscribers", help="manage the mailing list")
    subs_sub = subs_p.add_subparsers(dest="subscribers_command", required=True)

    sa = subs_sub.add_parser("add", help="add one subscriber")
    sa.add_argument("email")
    sa.add_argument("--name", default="")
    sa.add_argument("--tags", default="", help="comma-separated")
    sa.add_argument("--source", default="manual", help="where they opted in")
    sa.add_argument("--config", default=None)

    si = subs_sub.add_parser("import", help="merge a CSV of subscribers")
    si.add_argument("path")
    si.add_argument("--tags", default="", help="comma-separated tags to apply to all")
    si.add_argument("--source", default="import")
    si.add_argument("--config", default=None)

    su = subs_sub.add_parser("unsubscribe", help="unsubscribe by address or token")
    su.add_argument("--email", default="")
    su.add_argument("--token", default="")
    su.add_argument("--config", default=None)

    ss = subs_sub.add_parser("stats", help="show list counts")
    ss.add_argument("--config", default=None)

    args = parser.parse_args(argv)

    if args.command == "run":
        cfg = load_config(args.config)
        pipeline.run(cfg)
        return 0

    if args.command == "research":
        cfg = load_config(args.config)
        llm = LLM(
            model=cfg.llm.get("model", "claude-opus-4-8"),
            max_tokens=cfg.llm.get("max_tokens", 4000),
            temperature=cfg.llm.get("temperature", 0.7),
        )
        report = market_research.research(cfg.niche, cfg.brand, llm, notes=cfg.research_notes)
        print(report.to_markdown())
        return 0

    if args.command == "analytics":
        import json as _json
        cfg = load_config(args.config)
        llm = LLM(
            model=cfg.llm.get("model", "claude-opus-4-8"),
            max_tokens=cfg.llm.get("max_tokens", 4000),
            temperature=cfg.llm.get("temperature", 0.7),
        )
        with open(args.metrics, encoding="utf-8") as fh:
            metrics = _json.load(fh)
        report = analytics.analyze(metrics, cfg.brand, llm)
        print(report.to_markdown())
        return 0

    if args.command == "email":
        return _email(args)

    if args.command == "subscribers":
        return _subscribers(args)

    parser.print_help()
    return 1


def _email(args) -> int:
    cfg = load_config(args.config)

    if args.email_command == "build":
        email_pipeline.build(
            cfg,
            kind=args.kind,
            product_path=args.product,
            count=args.count,
            notes=args.notes,
            tag=args.tag,
            product_url=args.url,
        )
        return 0

    if args.email_command == "send":
        try:
            email_pipeline.send(
                cfg,
                args.campaign,
                live=args.live,
                index=args.index,
                drip=args.drip,
                tag=args.tag,
                limit=args.limit,
                backend=args.backend,
                test_to=args.test_to,
            )
        except email_pipeline.NotApproved as exc:
            print(f"✋ refusing to send: {exc}")
            return 2
        except FileNotFoundError as exc:
            print(f"✗ {exc}")
            return 2
        return 0

    if args.email_command == "list":
        campaigns = sorted(
            d for d in cfg.email_campaigns_dir.glob("*") if (d / "campaign.json").exists()
        )
        if not campaigns:
            print("No campaigns yet. Build one: python -m src.main email build --kind welcome")
            return 0
        for directory in campaigns:
            approval = email_pipeline.read_approval(cfg, directory.name)
            state = "approved" if approval.get("approved") else "awaiting approval"
            print(f"{directory.name}  [{state}]")
        return 0

    if args.email_command == "inbox":
        from src.agent import email_inbox
        from src.agent.email_list import SubscriberList

        settings = email_inbox.ImapSettings.from_config(cfg.email_settings_raw)
        if not settings.ready:
            print("✋ inbox not configured yet:")
            for gap in settings.missing():
                print(f"  - {gap}")
            return 2
        subscribers = SubscriberList.load(cfg.email_list_path)
        print(f"▶ reading {settings.user} for replies…")
        try:
            report = email_inbox.check(settings, subscribers, cfg.email_log_path, args.days)
        except Exception as exc:
            print(f"✗ could not read the inbox: {exc}")
            return 2
        subscribers.save()
        print(f"✓ {report.summary()}")
        for reply in report.replies:
            flag = "  [asked to stop]" if reply.opted_out else ""
            print(f"\n  ← {reply.email}{flag}\n    {reply.snippet[:160]}")
        return 0

    if args.email_command == "dashboard":
        from src.agent import email_dashboard
        from src.agent.email_list import SubscriberList

        subscribers = SubscriberList.load(cfg.email_list_path)
        out = email_dashboard.write(
            subscribers, cfg.email_log_path,
            cfg.email_campaigns_dir.parent / "inbox.html", args.name,
        )
        print(f"✓ dashboard: {out}")
        print(f"  open it: file://{out}")
        return 0

    if args.email_command == "preview":
        campaign, _ = email_pipeline.load_campaign(cfg, args.campaign)
        print(campaign.to_markdown())
        return 0

    return 1


def _subscribers(args) -> int:
    from src.agent.email_list import SubscriberList

    cfg = load_config(args.config)
    subscribers = SubscriberList.load(cfg.email_list_path)
    tags = [t.strip() for t in (getattr(args, "tags", "") or "").split(",") if t.strip()]

    if args.subscribers_command == "add":
        try:
            sub, created = subscribers.add(args.email, args.name, tags, args.source)
        except ValueError as exc:
            print(f"✗ {exc}")
            return 2
        subscribers.save()
        print(f"{'added' if created else 'updated'}: {sub.email} ({sub.status})")
        return 0

    if args.subscribers_command == "import":
        try:
            stats = subscribers.import_csv(args.path, source=args.source, tags=tags)
        except FileNotFoundError:
            print(f"✗ no such file: {args.path}")
            return 2
        subscribers.save()
        print(f"added {stats['added']}, updated {stats['updated']}, skipped {stats['skipped']}")
        return 0

    if args.subscribers_command == "unsubscribe":
        sub = subscribers.unsubscribe(email=args.email, token=args.token)
        if sub is None:
            print("✗ no subscriber matched")
            return 2
        subscribers.save()
        print(f"unsubscribed: {sub.email}")
        return 0

    if args.subscribers_command == "stats":
        stats = subscribers.stats()
        print(f"list: {cfg.email_list_path}")
        for key, value in stats.items():
            print(f"  {key}: {value}")
        return 0

    return 1


if __name__ == "__main__":
    raise SystemExit(main())
