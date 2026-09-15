"""Orchestrate email marketing: build a campaign, then (only on your yes) send it.

Same contract as the product pipeline. `build` writes files and an approval
request and stops. `send` refuses to touch the network until that approval says
approved and compliance passed — and even then defaults to the outbox, so the
first run of any campaign is always a rehearsal you can read.
"""

from __future__ import annotations

import datetime as _dt
import json
from pathlib import Path

from . import compliance
from .config import Config
from .email_campaign import Campaign, build_campaign, slugify
from .email_list import SubscriberList
from .email_sender import EmailSettings, Sender, due_emails, make_backend, resolve_recipients
from .llm import LLM


class NotApproved(RuntimeError):
    """Raised when a live send is attempted without a human yes."""


# ------------------------------------------------------------------ helpers

def _llm(cfg: Config) -> LLM:
    return LLM(
        model=cfg.llm.get("model", "claude-opus-4-8"),
        max_tokens=cfg.llm.get("max_tokens", 4000),
        temperature=cfg.llm.get("temperature", 0.7),
    )


def latest_product(cfg: Config) -> dict | None:
    """The most recent product run's meta.json, if there is one."""
    runs = sorted((d for d in cfg.output_dir.glob("*") if (d / "meta.json").exists()),
                  key=lambda d: d.name)
    if not runs:
        return None
    meta = json.loads((runs[-1] / "meta.json").read_text(encoding="utf-8"))
    product = dict(meta.get("product", {}))
    product["_run_dir"] = str(runs[-1])
    return product


def load_product(path: str | Path) -> dict:
    path = Path(path)
    meta_path = path if path.name == "meta.json" else path / "meta.json"
    meta = json.loads(meta_path.read_text(encoding="utf-8"))
    product = dict(meta.get("product", {}))
    product["_run_dir"] = str(meta_path.parent)
    return product


def campaign_dir(cfg: Config, slug: str) -> Path:
    """Find a campaign by slug or by its full directory name."""
    root = cfg.email_campaigns_dir
    exact = root / slug
    if (exact / "campaign.json").exists():
        return exact
    matches = sorted(d for d in root.glob(f"*{slug}*") if (d / "campaign.json").exists())
    if not matches:
        raise FileNotFoundError(
            f"No campaign matching {slug!r} in {root}. Run `email build` first."
        )
    return matches[-1]  # newest wins


def load_campaign(cfg: Config, slug: str) -> tuple[Campaign, Path]:
    directory = campaign_dir(cfg, slug)
    data = json.loads((directory / "campaign.json").read_text(encoding="utf-8"))
    return Campaign.from_dict(data), directory


def approval_path(cfg: Config, slug: str) -> Path:
    return cfg.approvals_dir / f"email-{slug}.json"


def read_approval(cfg: Config, slug: str) -> dict:
    path = approval_path(cfg, slug)
    if not path.exists():
        return {}
    return json.loads(path.read_text(encoding="utf-8"))


# -------------------------------------------------------------------- build

def build(
    cfg: Config,
    kind: str = "welcome",
    product_path: str | Path | None = None,
    count: int | None = None,
    notes: str = "",
    tag: str = "",
    product_url: str = "",
) -> Path:
    """Write a campaign + its approval request. Sends nothing."""
    llm = _llm(cfg)
    mode = "DRY-RUN (no API key)" if llm.dry_run else f"LIVE ({llm.model})"
    print(f"▶ cowock email build — {mode}")

    product = load_product(product_path) if product_path else latest_product(cfg)
    if product:
        print(f"  product: {product.get('title', '(untitled)')}")
    else:
        print("  no product found — writing a product-free campaign")

    print(f"  writing {kind} campaign…")
    campaign = build_campaign(
        kind,
        cfg.brand,
        llm,
        product=product,
        count=count,
        notes=notes or cfg.research_notes,
        audience_tag=tag or cfg.email_default_tag,
    )
    campaign.product_url = product_url or cfg.email_settings_raw.get("product_url", "")
    stamp = _dt.datetime.now().strftime("%Y%m%d-%H%M%S")
    campaign.slug = f"{stamp}-{kind}-{slugify(campaign.product_title or kind)}"
    campaign.created = stamp
    print(f"  → {len(campaign.emails)} email(s)")

    print("  running halal-compliance review…")
    verdict = compliance.review(campaign.combined_text(), cfg.halal_rules, llm)
    print(f"  → compliance ok={verdict.ok} score={verdict.score}")
    for issue in verdict.issues:
        print(f"     ⚠ {issue}")

    warnings = _field_warnings(campaign)
    for warning in warnings:
        print(f"     ⚠ {warning}")

    directory = cfg.email_campaigns_dir / campaign.slug
    directory.mkdir(parents=True, exist_ok=True)
    (directory / "campaign.json").write_text(
        json.dumps(campaign.to_dict(), indent=2), encoding="utf-8")
    (directory / "campaign.md").write_text(campaign.to_markdown(), encoding="utf-8")
    (directory / "meta.json").write_text(
        json.dumps(
            {
                "campaign": campaign.slug,
                "kind": kind,
                "created": stamp,
                "mode": mode,
                "compliance": verdict.to_dict(),
                "warnings": warnings,
                "product": product.get("title") if product else None,
            },
            indent=2,
        ),
        encoding="utf-8",
    )

    settings = EmailSettings.from_config(cfg.email_settings_raw)
    approval = {
        "approved": False,
        "campaign": campaign.slug,
        "kind": kind,
        "emails": [e.subject for e in campaign.emails],
        "audience_tag": campaign.audience_tag,
        "compliance_ok": verdict.ok,
        "compliance_score": verdict.score,
        "compliance_issues": verdict.issues,
        "warnings": warnings,
        "campaign_dir": str(directory),
        "missing_for_live_send": settings.missing_for_live(),
        "instructions": (
            "Read campaign.md in campaign_dir. Rehearse with "
            f"`python -m src.main email send --campaign {campaign.slug}` — that writes "
            ".eml files to the outbox and sends nothing. When you are happy, set "
            "'approved' to true here and add --live to really send."
        ),
    }
    path = approval_path(cfg, campaign.slug)
    path.write_text(json.dumps(approval, indent=2), encoding="utf-8")

    print(f"✓ campaign: {directory}")
    print(f"✓ approval request: {path}")
    return directory


def _field_warnings(campaign: Campaign) -> list[str]:
    """Merge fields the sender cannot fill would ship as blanks — flag them."""
    known = {"first_name", "name", "email", "sender_name", "brand",
             "product_title", "product_url", "price", "unsubscribe_url"}
    warnings: list[str] = []
    for i, mail in enumerate(campaign.emails, start=1):
        unknown = [f for f in mail.merge_fields() if f not in known]
        if unknown:
            warnings.append(f"email {i} uses unknown merge field(s): {', '.join(unknown)}")
        if "{{product_url}}" in (mail.cta_url or "") and not campaign.product_url:
            warnings.append(f"email {i} links to {{{{product_url}}}} but no product_url is set")
    return warnings


# --------------------------------------------------------------------- send

def send(
    cfg: Config,
    slug: str,
    live: bool = False,
    index: int | None = None,
    drip: bool = False,
    tag: str = "",
    limit: int | None = None,
    backend: str = "",
    test_to: str = "",
) -> list:
    """Send a campaign. Defaults to the outbox; --live is a deliberate choice."""
    campaign, directory = load_campaign(cfg, slug)
    settings = EmailSettings.from_config(cfg.email_settings_raw)
    approval = read_approval(cfg, campaign.slug)

    if live:
        _assert_sendable(cfg, campaign, approval, settings)

    backend_kind = backend or ("smtp" if live else "outbox")
    mode = "LIVE SEND" if backend_kind == "smtp" else f"rehearsal → {backend_kind}"
    print(f"▶ cowock email send — {campaign.name} ({mode})")

    subscribers = SubscriberList.load(cfg.email_list_path)
    if test_to:
        from .email_list import Subscriber
        recipients = [Subscriber(email=test_to, name="Test Recipient", source="test-send")]
        print(f"  test send to {test_to}")
    else:
        recipients = resolve_recipients(subscribers, campaign, tag)
        label = tag or campaign.audience_tag
        print(f"  {len(recipients)} active subscriber(s)"
              + (f" tagged '{label}'" if label else ""))

    if not recipients:
        print("  nothing to send — the list has no matching active subscribers")
        return []

    reports = []
    for email_index, batch in _plan(campaign, recipients, index, drip):
        if not batch:
            continue
        sender = Sender(settings, make_backend(backend_kind, settings, cfg.email_outbox_dir),
                        cfg.email_log_path)
        report = sender.send_campaign(campaign, batch, index=email_index, limit=limit)
        reports.append(report)
        print(f"  email {email_index + 1}/{len(campaign.emails)}: {report.summary()}")
        for result in report.results:
            if result.status == "failed":
                print(f"     ✗ {result.email}: {result.reason}")

    stamp = _dt.datetime.now().strftime("%Y%m%d-%H%M%S")
    report_path = directory / f"send-report-{stamp}.json"
    report_path.write_text(
        json.dumps([r.to_dict() for r in reports], indent=2), encoding="utf-8")
    print(f"✓ report: {report_path}")
    if backend_kind == "outbox":
        print(f"  open the .eml files in {cfg.email_outbox_dir} to proofread, "
              "then re-run with --live once approved.")
    return reports


def _plan(campaign: Campaign, recipients: list, index: int | None, drip: bool):
    """Which email goes to whom: one blast, or the drip schedule per subscriber."""
    if drip:
        buckets: dict[int, list] = {}
        for subscriber in recipients:
            for email_index in due_emails(subscriber, campaign):
                buckets.setdefault(email_index, []).append(subscriber)
        return sorted(buckets.items())
    return [(index or 0, list(recipients))]


def _assert_sendable(cfg: Config, campaign: Campaign, approval: dict,
                     settings: EmailSettings) -> None:
    """Everything that must be true before real mail goes out."""
    if not approval:
        raise NotApproved(
            f"No approval file at {approval_path(cfg, campaign.slug)}. Run `email build` first."
        )
    if not approval.get("approved"):
        raise NotApproved(
            f"Campaign '{campaign.slug}' is not approved. Read the campaign, then set "
            f'"approved": true in {approval_path(cfg, campaign.slug)}.'
        )
    if not approval.get("compliance_ok", False):
        raise NotApproved(
            f"Campaign '{campaign.slug}' failed the halal-compliance review "
            f"({'; '.join(approval.get('compliance_issues', [])) or 'see meta.json'}). "
            "Fix the copy and rebuild before sending."
        )
    missing = settings.missing_for_live()
    if missing:
        raise NotApproved(
            "Cannot send live until these are set:\n  - " + "\n  - ".join(missing)
        )
