"""The sender — the part that actually puts mail in inboxes.

Three backends, chosen by how real you want the run to be:

    outbox   (default) writes a .eml file per recipient, opens in any mail app
    console             prints subject + recipient, sends nothing
    smtp                really sends, over your own SMTP credentials

Sending is the one irreversible step in cowock — a sent email cannot be
recalled — so it is gated the same way publishing is: the campaign's approval
file must say approved, compliance must have passed, and live sending has to be
asked for explicitly. Everything else defaults to the outbox.

Every message carries a working unsubscribe link, List-Unsubscribe headers for
one-click unsubscribe in Gmail/Apple Mail, and your postal address — that is
both CAN-SPAM's requirement and plain honesty about who is writing.
"""

from __future__ import annotations

import datetime as _dt
import json
import os
import smtplib
import ssl
import time
from dataclasses import asdict, dataclass, field
from email.message import EmailMessage
from email.utils import formataddr, make_msgid
from pathlib import Path
from typing import Any, Iterable

from .email_campaign import Campaign, Email
from .email_list import Subscriber, SubscriberList


# Placeholders a config ships with. Mailing real people from "Your Name at
# Brand" is the kind of thing you only notice after the send, so it is blocked.
_PLACEHOLDER_NAMES = ("your name", "yourname", "your-name", "first name",
                      "firstname", "<name>", "todo")


def _is_placeholder(name: str) -> bool:
    lowered = (name or "").strip().lower()
    return any(marker in lowered for marker in _PLACEHOLDER_NAMES)


# ------------------------------------------------------------------ settings

@dataclass
class EmailSettings:
    from_name: str = "Cowock"
    from_email: str = ""
    reply_to: str = ""
    unsubscribe_url: str = ""          # may contain {token}
    unsubscribe_mailto: str = ""
    postal_address: str = ""
    rate_limit_per_minute: int = 20
    daily_limit: int = 400
    smtp_host: str = ""
    smtp_port: int = 587
    smtp_user: str = ""
    smtp_password: str = ""
    smtp_ssl: bool = False             # True = implicit TLS (port 465)
    # "optin" thanks them for subscribing; "cold" says plainly that this is
    # outreach. Telling a stranger they subscribed is simply a lie, and it is
    # the first thing a spam complaint quotes back at you.
    footer_mode: str = "optin"
    cold_intro: str = ""

    @classmethod
    def from_config(cls, raw: dict[str, Any] | None = None) -> "EmailSettings":
        """config.yaml values, with environment variables winning.

        Credentials only ever come from the environment — nothing secret belongs
        in a file that gets committed.
        """
        raw = raw or {}
        settings = cls(
            from_name=str(raw.get("from_name", "Cowock")),
            from_email=str(raw.get("from_email", "")),
            reply_to=str(raw.get("reply_to", "")),
            unsubscribe_url=str(raw.get("unsubscribe_url", "")),
            unsubscribe_mailto=str(raw.get("unsubscribe_mailto", "")),
            postal_address=str(raw.get("postal_address", "")),
            rate_limit_per_minute=int(raw.get("rate_limit_per_minute", 20) or 20),
            daily_limit=int(raw.get("daily_limit", 400) or 400),
            smtp_port=int(raw.get("smtp_port", 587) or 587),
            smtp_ssl=bool(raw.get("smtp_ssl", False)),
            footer_mode=str(raw.get("footer_mode", "optin")),
            cold_intro=str(raw.get("cold_intro", "")),
        )
        env = os.environ
        settings.from_email = env.get("EMAIL_FROM", settings.from_email)
        settings.from_name = env.get("EMAIL_FROM_NAME", settings.from_name)
        settings.reply_to = env.get("EMAIL_REPLY_TO", settings.reply_to)
        settings.smtp_host = env.get("SMTP_HOST", settings.smtp_host)
        settings.smtp_port = int(env.get("SMTP_PORT", settings.smtp_port) or settings.smtp_port)
        settings.smtp_user = env.get("SMTP_USER", settings.smtp_user)
        settings.smtp_password = env.get("SMTP_PASSWORD", settings.smtp_password)
        if env.get("SMTP_SSL"):
            settings.smtp_ssl = env["SMTP_SSL"].strip().lower() in ("1", "true", "yes")
        return settings

    @property
    def smtp_ready(self) -> bool:
        return bool(self.smtp_host and self.from_email)

    def sender_header(self) -> str:
        return formataddr((self.from_name, self.from_email or "cowock@localhost"))

    def unsubscribe_link(self, subscriber: Subscriber) -> str:
        if not self.unsubscribe_url:
            return ""
        url = self.unsubscribe_url
        for key, value in (("{token}", subscriber.token), ("{email}", subscriber.email)):
            url = url.replace(key, value)
        return url

    def _why_line(self) -> str:
        if self.footer_mode == "cold":
            return self.cold_intro or (
                f"You are getting this because I am reaching out to businesses in your "
                f"trade. I am {self.from_name}."
            )
        return f"You are receiving this because you subscribed to {self.from_name}."

    def footer_markdown(self, subscriber: Subscriber) -> str:
        """Why they got it, how to stop it, and who is writing."""
        lines: list[str] = []
        if self.from_name:
            lines.append(self._why_line())
        link = self.unsubscribe_link(subscriber)
        if link:
            lines.append(f"[Unsubscribe]({link}) at any time — one click, no questions.")
        elif self.unsubscribe_mailto:
            lines.append(f"To unsubscribe, reply to {self.unsubscribe_mailto} with 'unsubscribe'.")
        if self.postal_address:
            lines.append(self.postal_address)
        return "\n\n".join(lines)

    def footer_text(self, subscriber: Subscriber) -> str:
        lines: list[str] = []
        if self.from_name:
            lines.append(self._why_line())
        link = self.unsubscribe_link(subscriber)
        if link:
            lines.append(f"Unsubscribe: {link}")
        elif self.unsubscribe_mailto:
            lines.append(f"To unsubscribe, reply to {self.unsubscribe_mailto} with 'unsubscribe'.")
        if self.postal_address:
            lines.append(self.postal_address)
        return "\n".join(lines)

    def missing_for_live(self) -> list[str]:
        """What still has to be filled in before a live send is allowed."""
        missing: list[str] = []
        if not self.from_name.strip() or _is_placeholder(self.from_name):
            missing.append(
                f"email.from_name is still the placeholder ({self.from_name!r}) — "
                "put your own first name in front of the brand"
            )
        if not self.from_email:
            missing.append("EMAIL_FROM (sender address)")
        if not self.smtp_host:
            missing.append("SMTP_HOST")
        if not self.smtp_user:
            missing.append("SMTP_USER")
        if not self.smtp_password:
            missing.append("SMTP_PASSWORD")
        if not (self.unsubscribe_url or self.unsubscribe_mailto):
            missing.append("email.unsubscribe_url (or unsubscribe_mailto) in config.yaml")
        if not self.postal_address:
            missing.append("email.postal_address in config.yaml")
        return missing


# ------------------------------------------------------------------ backends

class Backend:
    """Anything that can take an EmailMessage somewhere."""

    name = "backend"
    live = False

    def __enter__(self) -> "Backend":
        return self

    def __exit__(self, *exc: Any) -> None:
        self.close()

    def send(self, message: EmailMessage) -> str:
        raise NotImplementedError

    def close(self) -> None:
        pass


class ConsoleBackend(Backend):
    """Prints what would go out. Sends nothing."""

    name = "console"

    def send(self, message: EmailMessage) -> str:
        print(f"    → {message['To']}  |  {message['Subject']}")
        return message["Message-ID"] or ""


class OutboxBackend(Backend):
    """Writes each message as a .eml file you can open and inspect."""

    name = "outbox"

    def __init__(self, directory: str | Path):
        self.directory = Path(directory)
        self.directory.mkdir(parents=True, exist_ok=True)

    def send(self, message: EmailMessage) -> str:
        stamp = _dt.datetime.now().strftime("%Y%m%d-%H%M%S-%f")
        safe = (message["To"] or "unknown").replace("@", "_at_").replace("/", "_")
        path = self.directory / f"{stamp}-{safe}.eml"
        path.write_bytes(bytes(message))
        return message["Message-ID"] or str(path)


class SMTPBackend(Backend):
    """Real delivery over SMTP (Gmail app password, Fastmail, SES, Postmark…)."""

    name = "smtp"
    live = True

    def __init__(self, settings: EmailSettings):
        self.settings = settings
        self._smtp: smtplib.SMTP | None = None

    def _connect(self) -> smtplib.SMTP:
        if self._smtp is not None:
            return self._smtp
        s = self.settings
        context = ssl.create_default_context()
        if s.smtp_ssl:
            smtp: smtplib.SMTP = smtplib.SMTP_SSL(s.smtp_host, s.smtp_port, context=context, timeout=30)
        else:
            smtp = smtplib.SMTP(s.smtp_host, s.smtp_port, timeout=30)
            smtp.ehlo()
            smtp.starttls(context=context)
            smtp.ehlo()
        if s.smtp_user and s.smtp_password:
            smtp.login(s.smtp_user, s.smtp_password)
        self._smtp = smtp
        return smtp

    def send(self, message: EmailMessage) -> str:
        self._connect().send_message(message)
        return message["Message-ID"] or ""

    def close(self) -> None:
        if self._smtp is not None:
            try:
                self._smtp.quit()
            except Exception:  # pragma: no cover - best-effort teardown
                pass
            self._smtp = None


def make_backend(kind: str, settings: EmailSettings, outbox_dir: str | Path) -> Backend:
    if kind == "smtp":
        if not settings.smtp_ready:
            raise ValueError("SMTP backend needs SMTP_HOST and EMAIL_FROM (see .env.example)")
        return SMTPBackend(settings)
    if kind == "console":
        return ConsoleBackend()
    if kind == "outbox":
        return OutboxBackend(outbox_dir)
    raise ValueError(f"unknown backend {kind!r}; expected smtp, outbox or console")


# ------------------------------------------------------------------- results

@dataclass
class SendResult:
    email: str
    status: str            # sent | skipped | failed
    reason: str = ""
    subject: str = ""
    message_id: str = ""
    email_index: int = 0


@dataclass
class SendReport:
    campaign: str
    backend: str
    live: bool
    started: str = ""
    finished: str = ""
    results: list[SendResult] = field(default_factory=list)

    def count(self, status: str) -> int:
        return sum(1 for r in self.results if r.status == status)

    @property
    def sent(self) -> int:
        return self.count("sent")

    @property
    def skipped(self) -> int:
        return self.count("skipped")

    @property
    def failed(self) -> int:
        return self.count("failed")

    def to_dict(self) -> dict:
        return {
            "campaign": self.campaign,
            "backend": self.backend,
            "live": self.live,
            "started": self.started,
            "finished": self.finished,
            "sent": self.sent,
            "skipped": self.skipped,
            "failed": self.failed,
            "results": [asdict(r) for r in self.results],
        }

    def summary(self) -> str:
        mode = "LIVE" if self.live else f"{self.backend} (nothing left this machine)"
        return (f"{self.campaign}: {self.sent} sent, {self.skipped} skipped, "
                f"{self.failed} failed — {mode}")


# -------------------------------------------------------------------- sender

class Sender:
    """Builds, throttles, logs and delivers a campaign's messages."""

    def __init__(
        self,
        settings: EmailSettings,
        backend: Backend,
        log_path: str | Path,
        sleep: Any = time.sleep,
    ):
        self.settings = settings
        self.backend = backend
        self.log_path = Path(log_path)
        self._sleep = sleep
        self._already_sent = self._load_log()

    # --------------------------------------------------------------- log

    @staticmethod
    def _key(campaign_slug: str, index: int, address: str) -> str:
        return f"{campaign_slug}:{index}:{address.lower()}"

    def _load_log(self) -> set[str]:
        """Which (campaign, email, recipient) triples already went out.

        This is what makes re-running a send safe: nobody gets the same email
        twice because a cron job fired again or a send died halfway.
        """
        sent: set[str] = set()
        if not self.log_path.exists():
            return sent
        with self.log_path.open("r", encoding="utf-8") as fh:
            for line in fh:
                line = line.strip()
                if not line:
                    continue
                try:
                    entry = json.loads(line)
                except json.JSONDecodeError:
                    continue
                if entry.get("status") == "sent":
                    sent.add(self._key(entry.get("campaign", ""), int(entry.get("email_index", 0)),
                                       entry.get("email", "")))
        return sent

    def _log(self, campaign_slug: str, result: SendResult) -> None:
        self.log_path.parent.mkdir(parents=True, exist_ok=True)
        entry = {"ts": _dt.datetime.now().isoformat(timespec="seconds"),
                 "campaign": campaign_slug, **asdict(result)}
        with self.log_path.open("a", encoding="utf-8") as fh:
            fh.write(json.dumps(entry) + "\n")

    def sent_today(self) -> int:
        today = _dt.date.today().isoformat()
        if not self.log_path.exists():
            return 0
        count = 0
        with self.log_path.open("r", encoding="utf-8") as fh:
            for line in fh:
                try:
                    entry = json.loads(line)
                except json.JSONDecodeError:
                    continue
                if entry.get("status") == "sent" and str(entry.get("ts", "")).startswith(today):
                    count += 1
        return count

    # ------------------------------------------------------------ compose

    def context(self, subscriber: Subscriber, campaign: Campaign,
                extra: dict[str, str] | None = None) -> dict[str, str]:
        ctx = {
            "first_name": subscriber.first_name,
            "name": subscriber.name,
            "email": subscriber.email,
            "sender_name": self.settings.from_name,
            "brand": self.settings.from_name,
            "product_title": campaign.product_title,
            "product_url": campaign.product_url,
            "price": f"${campaign.price_usd:.0f}" if campaign.price_usd else "",
            "unsubscribe_url": self.settings.unsubscribe_link(subscriber),
        }
        ctx.update(subscriber.fields)  # company, city, trade… from the CSV
        ctx.update(extra or {})
        return ctx

    def build_message(self, mail: Email, subscriber: Subscriber, campaign: Campaign,
                      index: int = 0, extra: dict[str, str] | None = None) -> EmailMessage:
        ctx = self.context(subscriber, campaign, extra)
        message = EmailMessage()
        message["Subject"] = mail.render_subject(ctx)
        message["From"] = self.settings.sender_header()
        message["To"] = subscriber.email
        message["Message-ID"] = make_msgid()
        message["Date"] = _dt.datetime.now(_dt.timezone.utc).strftime("%a, %d %b %Y %H:%M:%S %z")
        if self.settings.reply_to:
            message["Reply-To"] = self.settings.reply_to
        message["X-Campaign"] = f"{campaign.slug}:{index}"

        # One-click unsubscribe, the way Gmail and Apple Mail expect it.
        targets = []
        link = self.settings.unsubscribe_link(subscriber)
        if link:
            targets.append(f"<{link}>")
        if self.settings.unsubscribe_mailto:
            targets.append(f"<mailto:{self.settings.unsubscribe_mailto}?subject=unsubscribe>")
        if targets:
            message["List-Unsubscribe"] = ", ".join(targets)
            if link:
                message["List-Unsubscribe-Post"] = "List-Unsubscribe=One-Click"

        message.set_content(mail.render_text(ctx, footer=self.settings.footer_text(subscriber)))
        message.add_alternative(
            mail.render_html(ctx, footer=self.settings.footer_markdown(subscriber)),
            subtype="html",
        )
        return message

    # --------------------------------------------------------------- send

    def send_campaign(
        self,
        campaign: Campaign,
        recipients: Iterable[Subscriber],
        index: int = 0,
        limit: int | None = None,
        extra: dict[str, str] | None = None,
    ) -> SendReport:
        """Send one email of the campaign to each recipient."""
        if not campaign.emails:
            raise ValueError("campaign has no emails")
        if not 0 <= index < len(campaign.emails):
            raise IndexError(f"email index {index} out of range (0-{len(campaign.emails) - 1})")

        mail = campaign.emails[index]
        report = SendReport(
            campaign=campaign.slug,
            backend=self.backend.name,
            live=self.backend.live,
            started=_dt.datetime.now().isoformat(timespec="seconds"),
        )
        delay = 60.0 / max(self.settings.rate_limit_per_minute, 1)
        budget = self.settings.daily_limit - self.sent_today() if self.backend.live else None
        first = True

        with self.backend:
            for subscriber in recipients:
                if limit is not None and report.sent >= limit:
                    break
                result = self._send_one(campaign, mail, subscriber, index, extra, budget, delay, first)
                if result.status == "sent":
                    first = False
                    if budget is not None:
                        budget -= 1
                report.results.append(result)
                self._log(campaign.slug, result)

        report.finished = _dt.datetime.now().isoformat(timespec="seconds")
        return report

    def _send_one(self, campaign: Campaign, mail: Email, subscriber: Subscriber, index: int,
                  extra: dict[str, str] | None, budget: int | None, delay: float,
                  first: bool) -> SendResult:
        base = SendResult(email=subscriber.email, status="skipped", subject=mail.subject,
                          email_index=index)
        if not subscriber.active:
            base.reason = f"status is {subscriber.status}"
            return base
        if self._key(campaign.slug, index, subscriber.email) in self._already_sent:
            base.reason = "already sent (see send log)"
            return base
        if budget is not None and budget <= 0:
            base.reason = f"daily limit of {self.settings.daily_limit} reached"
            return base

        if not first:  # throttle between sends, never before the first
            self._sleep(delay)

        try:
            message = self.build_message(mail, subscriber, campaign, index, extra)
            message_id = self.backend.send(message)
        except Exception as exc:  # a bad address must not kill the whole run
            return SendResult(email=subscriber.email, status="failed", reason=f"{type(exc).__name__}: {exc}",
                              subject=mail.subject, email_index=index)

        self._already_sent.add(self._key(campaign.slug, index, subscriber.email))
        return SendResult(email=subscriber.email, status="sent", subject=message["Subject"],
                          message_id=message_id, email_index=index)


# ---------------------------------------------------------------------- drip

def due_emails(subscriber: Subscriber, campaign: Campaign,
               today: _dt.date | None = None) -> list[int]:
    """Indexes of the sequence emails this subscriber has now earned.

    A welcome sequence with delays [0, 2, 5] means: email 1 the day they join,
    email 2 two days later, email 3 on day five. Already-sent ones are filtered
    out by the send log, not here.
    """
    today = today or _dt.date.today()
    age_days = (today - subscriber.joined_date()).days
    return [i for i, mail in enumerate(campaign.emails) if mail.delay_days <= age_days]


def resolve_recipients(subscribers: SubscriberList, campaign: Campaign,
                       tag: str = "") -> list[Subscriber]:
    return subscribers.active(tag or campaign.audience_tag)
