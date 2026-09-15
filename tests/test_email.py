"""Email marketing tests — all offline, no API key and no network needed."""

import json
import os
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from src.agent import email_campaign, email_pipeline
from src.agent.config import Config
from src.agent.email_campaign import Email, build_campaign, markdown_to_html, render_fields
from src.agent.email_list import Subscriber, SubscriberList
from src.agent.email_sender import (
    ConsoleBackend,
    EmailSettings,
    OutboxBackend,
    SendResult,
    Sender,
    due_emails,
)
from src.agent.llm import LLM


def _dry_run_env():
    os.environ.pop("ANTHROPIC_API_KEY", None)
    for key in ("EMAIL_FROM", "SMTP_HOST", "SMTP_USER", "SMTP_PASSWORD"):
        os.environ.pop(key, None)


def _settings(**overrides):
    base = dict(
        from_name="Cowock",
        from_email="hello@cowock.test",
        unsubscribe_url="https://cowock.test/u?t={token}",
        postal_address="Cowock, 1 Main St, Austin TX",
        rate_limit_per_minute=600,
    )
    base.update(overrides)
    return EmailSettings(**base)


def _campaign(kind="welcome", **overrides):
    _dry_run_env()
    campaign = build_campaign(kind, {"voice": "warm"}, LLM(model="claude-opus-4-8"),
                              product={"title": "Budget Planner", "price_usd": 12.0})
    campaign.product_url = "https://cowock.test/planner"
    for key, value in overrides.items():
        setattr(campaign, key, value)
    return campaign


def _config(tmp: Path, **email_overrides) -> Config:
    email = {
        "list_path": str(tmp / "subscribers.csv"),
        "campaigns_dir": str(tmp / "campaigns"),
        "outbox_dir": str(tmp / "outbox"),
        "log_path": str(tmp / "send-log.jsonl"),
        "from_name": "Cowock",
        "rate_limit_per_minute": 600,
    }
    email.update(email_overrides)
    cfg = Config(raw={
        "niche": "test niche",
        "brand": {"voice": "warm", "audience": "moms"},
        "email": email,
        "output_dir": str(tmp / "products"),
        "approvals_dir": str(tmp / "approvals"),
    })
    cfg.validate()
    return cfg


# ----------------------------------------------------------------- the list

def test_list_add_is_idempotent_and_validates():
    with tempfile.TemporaryDirectory() as tmp:
        subs = SubscriberList(Path(tmp) / "list.csv")
        first, created = subs.add("Amina@Example.com ", "Amina Yusuf", ["moms"], "freebie")
        assert created is True and first.email == "amina@example.com"
        again, created = subs.add("amina@example.com", tags=["budget"])
        assert created is False and again.has_tag("budget") and len(subs) == 1
        try:
            subs.add("not-an-email")
            raise AssertionError("expected ValueError for a malformed address")
        except ValueError:
            pass


def test_unsubscribe_is_sticky_and_token_addressable():
    with tempfile.TemporaryDirectory() as tmp:
        subs = SubscriberList(Path(tmp) / "list.csv")
        sub, _ = subs.add("sara@example.com", "Sara Ahmed")
        assert subs.unsubscribe(token=sub.token) is sub
        assert sub.status == "unsubscribed"
        # A plain re-add must never put someone back on the list.
        subs.add("sara@example.com", tags=["moms"])
        assert sub.status == "unsubscribed"
        subs.add("sara@example.com", resubscribe=True)
        assert sub.status == "subscribed"


def test_list_round_trips_through_csv():
    with tempfile.TemporaryDirectory() as tmp:
        path = Path(tmp) / "list.csv"
        subs = SubscriberList(path)
        sub, _ = subs.add("amina@example.com", "Amina Yusuf", ["moms", "budget"], "freebie")
        subs.unsubscribe(email="amina@example.com")
        subs.save()
        reloaded = SubscriberList.load(path)
        back = reloaded.get("amina@example.com")
        assert back is not None and back.status == "unsubscribed"
        assert back.tags == ["moms", "budget"] and back.token == sub.token


def test_import_respects_an_unsubscribed_row():
    with tempfile.TemporaryDirectory() as tmp:
        source = Path(tmp) / "in.csv"
        source.write_text(
            "email,name,status,tags,source,joined,token\n"
            "layla@example.com,Layla,unsubscribed,moms,old-list,2026-08-20,tok123\n"
            "amina@example.com,Amina,subscribed,moms,old-list,2026-09-01,tok456\n"
            "junk,,,,,,\n",
            encoding="utf-8",
        )
        subs = SubscriberList(Path(tmp) / "list.csv")
        stats = subs.import_csv(source)
        assert stats == {"added": 2, "updated": 0, "skipped": 1}
        assert subs.get("layla@example.com").status == "unsubscribed"
        assert subs.get("layla@example.com").token == "tok123"
        assert [s.email for s in subs.active()] == ["amina@example.com"]


# ------------------------------------------------------------- the copy

def test_merge_fields_render_and_unknown_ones_are_dropped():
    ctx = {"first_name": "Amina", "sender_name": "Cowock"}
    out = render_fields("Hi {{first_name}}, from {{sender_name}}. {{mystery}}", ctx)
    assert "Amina" in out and "Cowock" in out
    assert "{{" not in out and "mystery" not in out
    # A missing first name must not leave 'Hi ,' in someone's inbox.
    assert render_fields("Hi {{first_name}},", {}).startswith("Hi,")


def test_markdown_to_html_covers_the_email_subset():
    html = markdown_to_html("## Title\n\nSome **bold** and *italic* text.\n\n- one\n- two\n")
    assert "<h3>Title</h3>" in html
    assert "<strong>bold</strong>" in html and "<em>italic</em>" in html
    assert "<li>one</li>" in html and "<ul>" in html
    assert "<script>" not in markdown_to_html("<script>alert(1)</script>")


def test_cta_is_dropped_when_its_link_is_empty():
    mail = Email(subject="s", body_markdown="body", cta_label="Get it",
                 cta_url="{{product_url}}")
    assert "Get it" not in mail.render_text({})
    assert "<a href" not in mail.render_html({})
    assert "https://cowock.test/x" in mail.render_text({"product_url": "https://cowock.test/x"})


def test_build_campaign_dry_run_has_structure_and_drip_delays():
    campaign = _campaign("welcome")
    assert len(campaign.emails) == 3
    assert all(e.subject and e.body_markdown for e in campaign.emails)
    assert [e.delay_days for e in campaign.emails] == [0, 2, 5]
    assert "Budget Planner" in campaign.to_markdown()
    restored = email_campaign.Campaign.from_dict(campaign.to_dict())
    assert restored.to_dict() == campaign.to_dict()
    try:
        build_campaign("spam-blast", {}, LLM(model="m"))
        raise AssertionError("expected ValueError for an unknown campaign kind")
    except ValueError:
        pass


# ----------------------------------------------------------------- sending

def test_message_carries_unsubscribe_footer_and_headers():
    with tempfile.TemporaryDirectory() as tmp:
        campaign = _campaign()
        sub = Subscriber(email="amina@example.com", name="Amina Yusuf")
        sender = Sender(_settings(), ConsoleBackend(), Path(tmp) / "log.jsonl")
        message = sender.build_message(campaign.emails[0], sub, campaign, index=0)
        assert message["To"] == "amina@example.com"
        assert message["From"] == "Cowock <hello@cowock.test>"
        assert sub.token in message["List-Unsubscribe"]
        assert message["List-Unsubscribe-Post"] == "List-Unsubscribe=One-Click"
        body = message.get_body("plain").get_content()
        html = message.get_body("html").get_content()
        assert "Hi Amina," in body and sub.token in body
        assert "1 Main St" in body and "1 Main St" in html
        assert "{{" not in body and "{{" not in html


def test_send_skips_unsubscribed_and_never_repeats_itself():
    with tempfile.TemporaryDirectory() as tmp:
        log = Path(tmp) / "log.jsonl"
        campaign = _campaign()
        active = Subscriber(email="amina@example.com", name="Amina")
        gone = Subscriber(email="layla@example.com", status="unsubscribed")
        sender = Sender(_settings(), ConsoleBackend(), log, sleep=lambda _: None)
        report = sender.send_campaign(campaign, [active, gone], index=0)
        assert report.sent == 1 and report.skipped == 1
        assert "unsubscribed" in report.results[1].reason

        # A second run (cron fired twice, a crash mid-send) must not re-mail.
        again = Sender(_settings(), ConsoleBackend(), log, sleep=lambda _: None)
        report2 = again.send_campaign(campaign, [active], index=0)
        assert report2.sent == 0 and "already sent" in report2.results[0].reason
        # …but the next email in the sequence is a different send.
        report3 = again.send_campaign(campaign, [active], index=1)
        assert report3.sent == 1


def test_one_bad_address_does_not_abort_the_run():
    class FlakyBackend(ConsoleBackend):
        def send(self, message):
            if message["To"] == "broken@example.com":
                raise OSError("mailbox unavailable")
            return "ok"

    with tempfile.TemporaryDirectory() as tmp:
        campaign = _campaign()
        people = [Subscriber(email="broken@example.com"), Subscriber(email="fine@example.com")]
        sender = Sender(_settings(), FlakyBackend(), Path(tmp) / "log.jsonl", sleep=lambda _: None)
        report = sender.send_campaign(campaign, people, index=0)
        assert report.failed == 1 and report.sent == 1
        assert "mailbox unavailable" in report.results[0].reason


def test_throttle_and_daily_limit_are_enforced():
    with tempfile.TemporaryDirectory() as tmp:
        slept: list[float] = []
        campaign = _campaign()
        people = [Subscriber(email=f"p{i}@example.com") for i in range(3)]
        sender = Sender(_settings(rate_limit_per_minute=30), ConsoleBackend(),
                        Path(tmp) / "log.jsonl", sleep=slept.append)
        report = sender.send_campaign(campaign, people, index=0)
        assert report.sent == 3
        assert slept == [2.0, 2.0]  # 30/minute, and never before the first send

        # The daily cap only applies to live backends; the outbox is free.
        log = Path(tmp) / "live-log.jsonl"
        live = Sender(_settings(daily_limit=1), ConsoleBackend(), log, sleep=lambda _: None)
        live.backend.live = True
        capped = live.send_campaign(campaign, people, index=0)
        assert capped.sent == 1 and capped.skipped == 2
        assert "daily limit" in capped.results[1].reason


def test_outbox_backend_writes_readable_eml():
    with tempfile.TemporaryDirectory() as tmp:
        outbox = Path(tmp) / "outbox"
        campaign = _campaign()
        sender = Sender(_settings(), OutboxBackend(outbox), Path(tmp) / "log.jsonl",
                        sleep=lambda _: None)
        sender.send_campaign(campaign, [Subscriber(email="amina@example.com", name="Amina")], index=0)
        files = list(outbox.glob("*.eml"))
        assert len(files) == 1
        raw = files[0].read_text(encoding="utf-8")
        assert "Subject:" in raw and "multipart/alternative" in raw


def test_due_emails_follows_the_drip_schedule():
    campaign = _campaign("welcome")  # delays 0, 2, 5
    import datetime as dt
    today = dt.date(2026, 9, 15)
    fresh = Subscriber(email="new@example.com", joined="2026-09-15")
    midway = Subscriber(email="mid@example.com", joined="2026-09-12")
    old = Subscriber(email="old@example.com", joined="2026-08-01")
    assert due_emails(fresh, campaign, today) == [0]
    assert due_emails(midway, campaign, today) == [0, 1]
    assert due_emails(old, campaign, today) == [0, 1, 2]


# ---------------------------------------------------------------- pipeline

def test_build_writes_campaign_and_an_unapproved_request():
    _dry_run_env()
    with tempfile.TemporaryDirectory() as tmp:
        cfg = _config(Path(tmp))
        directory = email_pipeline.build(cfg, kind="welcome", tag="moms")
        assert (directory / "campaign.json").exists()
        assert (directory / "campaign.md").exists()
        meta = json.loads((directory / "meta.json").read_text())
        assert meta["compliance"]["ok"] is True
        approval = json.loads(
            (cfg.approvals_dir / f"email-{directory.name}.json").read_text())
        assert approval["approved"] is False
        assert approval["audience_tag"] == "moms"
        assert len(approval["emails"]) == 3


def test_live_send_is_refused_until_approved_and_configured():
    _dry_run_env()
    with tempfile.TemporaryDirectory() as tmp:
        cfg = _config(Path(tmp))
        directory = email_pipeline.build(cfg, kind="launch")
        SubscriberList(cfg.email_list_path, [Subscriber(email="amina@example.com")]).save()

        for expected in ("not approved",):
            try:
                email_pipeline.send(cfg, directory.name, live=True)
                raise AssertionError("expected NotApproved")
            except email_pipeline.NotApproved as exc:
                assert expected in str(exc)

        approval_path = cfg.approvals_dir / f"email-{directory.name}.json"
        approval = json.loads(approval_path.read_text())
        approval["approved"] = True
        approval_path.write_text(json.dumps(approval))

        # Approved, but the sender is still unconfigured — still refused.
        try:
            email_pipeline.send(cfg, directory.name, live=True)
            raise AssertionError("expected NotApproved for missing settings")
        except email_pipeline.NotApproved as exc:
            assert "SMTP_HOST" in str(exc) and "unsubscribe_url" in str(exc)


def test_failed_compliance_blocks_a_live_send():
    _dry_run_env()
    with tempfile.TemporaryDirectory() as tmp:
        cfg = _config(Path(tmp))
        directory = email_pipeline.build(cfg, kind="broadcast")
        approval_path = cfg.approvals_dir / f"email-{directory.name}.json"
        approval = json.loads(approval_path.read_text())
        approval.update({"approved": True, "compliance_ok": False,
                         "compliance_issues": ["keyword match: casino"]})
        approval_path.write_text(json.dumps(approval))
        try:
            email_pipeline.send(cfg, directory.name, live=True)
            raise AssertionError("expected NotApproved for failed compliance")
        except email_pipeline.NotApproved as exc:
            assert "compliance" in str(exc)


def test_rehearsal_send_needs_no_approval_and_writes_to_the_outbox():
    _dry_run_env()
    with tempfile.TemporaryDirectory() as tmp:
        cfg = _config(Path(tmp))
        directory = email_pipeline.build(cfg, kind="welcome", tag="moms")
        subs = SubscriberList(cfg.email_list_path)
        subs.add("amina@example.com", "Amina", ["moms"], "test")
        subs.add("hana@example.com", "Hana", ["other"], "test")
        subs.save()

        reports = email_pipeline.send(cfg, directory.name)          # no --live
        assert len(reports) == 1 and reports[0].sent == 1            # tag filtered
        assert reports[0].live is False
        assert len(list(cfg.email_outbox_dir.glob("*.eml"))) == 1
        assert list(directory.glob("send-report-*.json"))

        drip = email_pipeline.send(cfg, directory.name, drip=True, tag="moms")
        assert sum(r.sent for r in drip) == 0  # email 1 already went, 2 and 3 not due


def test_test_send_targets_only_the_given_address():
    _dry_run_env()
    with tempfile.TemporaryDirectory() as tmp:
        cfg = _config(Path(tmp))
        directory = email_pipeline.build(cfg, kind="broadcast")
        subs = SubscriberList(cfg.email_list_path)
        subs.add("real@example.com", "Real Subscriber")
        subs.save()
        reports = email_pipeline.send(cfg, directory.name, test_to="me@example.com")
        assert reports[0].sent == 1
        assert reports[0].results[0].email == "me@example.com"


if __name__ == "__main__":
    tests = [value for name, value in sorted(globals().items()) if name.startswith("test_")]
    for test in tests:
        test()
        print(f"  ✓ {test.__name__}")
    print(f"OK — {len(tests)} email tests passed")
