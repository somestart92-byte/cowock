"""The reply side — reading the inbox, so outreach is a conversation not a blast.

A sender without an inbox is the thing that makes cold email hated: it keeps
chasing a man who already wrote back saying yes. This module reads replies over
IMAP, matches each one to the message that provoked it, and updates the list so
the sequence stops for that person automatically.

It also honours "stop" and "unsubscribe" in a reply body immediately, which is
both the law and the cheapest way to avoid a spam complaint.
"""

from __future__ import annotations

import datetime as _dt
import email as _email
import email.policy
import imaplib
import json
import os
import re
from dataclasses import asdict, dataclass, field
from email.utils import parseaddr
from pathlib import Path
from typing import Any

from .email_list import REPLIED, UNSUBSCRIBED, SubscriberList

# A reply whose whole point is "leave me alone". Checked against the first part
# of the body so a quoted original underneath cannot trigger it by accident.
_OPT_OUT = re.compile(
    r"\b(stop|unsubscribe|remove me|take me off|opt out|no thanks|not interested)\b",
    re.I,
)


@dataclass
class ImapSettings:
    host: str = ""
    port: int = 993
    user: str = ""
    password: str = ""
    mailbox: str = "INBOX"

    @classmethod
    def from_config(cls, raw: dict[str, Any] | None = None) -> "ImapSettings":
        """IMAP details, defaulting to the SMTP login — same mailbox, usually."""
        raw = raw or {}
        env = os.environ
        return cls(
            host=env.get("IMAP_HOST", str(raw.get("imap_host", ""))) or _guess_host(env, raw),
            port=int(env.get("IMAP_PORT", raw.get("imap_port", 993)) or 993),
            user=env.get("IMAP_USER", env.get("SMTP_USER", str(raw.get("imap_user", "")))),
            password=env.get("IMAP_PASSWORD", env.get("SMTP_PASSWORD", "")),
            mailbox=str(raw.get("mailbox", "INBOX")),
        )

    @property
    def ready(self) -> bool:
        return bool(self.host and self.user and self.password)

    def missing(self) -> list[str]:
        gaps = []
        if not self.host:
            gaps.append("IMAP_HOST (imap.gmail.com for Gmail)")
        if not self.user:
            gaps.append("IMAP_USER or SMTP_USER")
        if not self.password:
            gaps.append("IMAP_PASSWORD or SMTP_PASSWORD (a Gmail App Password)")
        return gaps


def _guess_host(env: dict[str, str], raw: dict[str, Any]) -> str:
    """smtp.gmail.com implies imap.gmail.com — save the user one setting."""
    smtp = env.get("SMTP_HOST", str(raw.get("smtp_host", "")))
    if smtp.startswith("smtp."):
        return "imap." + smtp[len("smtp."):]
    return ""


# A cold-outreach inbox is mostly noise: bounces, autoresponders, and "not now".
# Sorting it is what turns a pile of mail into a list of people to call.
INTERESTED = "interested"
QUESTION = "question"
NOT_INTERESTED = "not_interested"
AUTO_REPLY = "auto_reply"
UNCLEAR = "unclear"

_AUTO = re.compile(
    r"\b(out of (the )?office|automatic reply|auto-?reply|on (vacation|leave|holiday)|"
    r"away from my desk|currently away|undeliverable|delivery status notification)\b", re.I)
_INTERESTED = re.compile(
    r"\b(interested|sounds good|tell me more|how much|what.?s the (cost|price)|"
    r"send (me )?(the )?(info|details|more)|let.?s (talk|chat)|call me|"
    r"set(ting)? (it|that) up|i.?m in|yes please|sign me up|book (a|the) call)\b", re.I)
_QUESTION = re.compile(r"\?")


def classify(snippet: str) -> str:
    """Sort a reply into something actionable. Order matters: an out-of-office
    that happens to contain a question mark is still an out-of-office."""
    text = (snippet or "").strip()
    if not text:
        return UNCLEAR
    head = text[:400]
    if _AUTO.search(head):
        return AUTO_REPLY
    if _OPT_OUT.search(head[:200]):
        return NOT_INTERESTED
    if _INTERESTED.search(head):
        return INTERESTED
    if _QUESTION.search(head):
        return QUESTION
    return UNCLEAR


@dataclass
class Reply:
    email: str
    name: str = ""
    subject: str = ""
    snippet: str = ""
    received: str = ""
    message_id: str = ""
    in_reply_to: str = ""
    opted_out: bool = False
    kind: str = ""

    def __post_init__(self) -> None:
        # Classify here rather than at the call site, so a Reply is always
        # consistent however it was built — from IMAP, a test, or a fixture.
        if not self.kind:
            self.kind = classify(self.snippet)
        if not self.opted_out:
            self.opted_out = self.kind == NOT_INTERESTED

    def to_dict(self) -> dict:
        return asdict(self)


@dataclass
class InboxReport:
    replies: list[Reply] = field(default_factory=list)
    matched: int = 0          # replies traced to someone on the list
    opted_out: int = 0
    interested: int = 0
    checked: str = ""

    def to_dict(self) -> dict:
        return {
            "checked": self.checked,
            "matched": self.matched,
            "opted_out": self.opted_out,
            "interested": self.interested,
            "replies": [r.to_dict() for r in self.replies],
        }

    def summary(self) -> str:
        return (f"{len(self.replies)} reply(s) found, {self.matched} from people on "
                f"your list, {self.interested} look interested, "
                f"{self.opted_out} asked to stop")


def _body_snippet(message, limit: int = 400) -> str:
    """The reply itself, with the quoted original trimmed off where possible."""
    try:
        part = message.get_body(preferencelist=("plain",))
        text = part.get_content() if part else ""
    except Exception:
        text = ""
    if not text:
        return ""
    lines: list[str] = []
    for line in text.splitlines():
        stripped = line.strip()
        if stripped.startswith(">"):
            break
        if re.match(r"^On .+ wrote:$", stripped) or stripped.startswith("-----Original"):
            break
        lines.append(line)
    return "\n".join(lines).strip()[:limit]


def fetch_replies(settings: ImapSettings, since_days: int = 30,
                  known_message_ids: set[str] | None = None,
                  known_addresses: set[str] | None = None) -> list[Reply]:
    """Pull replies out of the mailbox over IMAP.

    A message counts as a reply when its In-Reply-To points at something we
    sent, or when it simply comes from an address on the list — people often
    write a fresh mail rather than hitting reply.
    """
    if not settings.ready:
        raise ValueError("IMAP is not configured: " + "; ".join(settings.missing()))

    known_message_ids = known_message_ids or set()
    known_addresses = {a.lower() for a in (known_addresses or set())}
    since = (_dt.date.today() - _dt.timedelta(days=since_days)).strftime("%d-%b-%Y")

    replies: list[Reply] = []
    conn = imaplib.IMAP4_SSL(settings.host, settings.port)
    try:
        conn.login(settings.user, settings.password)
        conn.select(settings.mailbox, readonly=True)
        status, data = conn.search(None, f'(SINCE {since})')
        if status != "OK":
            return replies
        for num in (data[0].split() if data and data[0] else []):
            status, raw = conn.fetch(num, "(RFC822)")
            if status != "OK" or not raw or not isinstance(raw[0], tuple):
                continue
            message = _email.message_from_bytes(raw[0][1], policy=email.policy.default)
            sender = parseaddr(str(message.get("From", "")))
            address = (sender[1] or "").lower()
            in_reply_to = str(message.get("In-Reply-To", "")).strip()

            is_reply = in_reply_to in known_message_ids if in_reply_to else False
            if not is_reply and address in known_addresses:
                is_reply = True
            if not is_reply:
                continue

            snippet = _body_snippet(message)
            replies.append(
                Reply(
                    email=address,
                    name=sender[0] or "",
                    subject=str(message.get("Subject", "")),
                    snippet=snippet,
                    received=str(message.get("Date", "")),
                    message_id=str(message.get("Message-ID", "")).strip(),
                    in_reply_to=in_reply_to,
                    opted_out=bool(_OPT_OUT.search(snippet[:200])),
                )
            )
    finally:
        try:
            conn.logout()
        except Exception:  # pragma: no cover - best-effort teardown
            pass
    return replies


def sent_message_ids(log_path: str | Path) -> tuple[set[str], set[str]]:
    """Message-IDs we sent, and who we sent them to — the keys for matching."""
    ids: set[str] = set()
    addresses: set[str] = set()
    path = Path(log_path)
    if not path.exists():
        return ids, addresses
    with path.open("r", encoding="utf-8") as fh:
        for line in fh:
            try:
                entry = json.loads(line)
            except json.JSONDecodeError:
                continue
            if entry.get("status") != "sent":
                continue
            if entry.get("message_id"):
                ids.add(entry["message_id"])
            if entry.get("email"):
                addresses.add(entry["email"].lower())
    return ids, addresses


def reconcile(subscribers: SubscriberList, replies: list[Reply]) -> InboxReport:
    """Apply what the inbox says to the list.

    Someone who replied stops receiving the sequence — that is the whole point.
    Someone who asked to stop is unsubscribed outright, which is stronger.
    """
    report = InboxReport(checked=_dt.datetime.now().isoformat(timespec="seconds"),
                         replies=replies)
    for reply in replies:
        sub = subscribers.get(reply.email)
        if sub is None:
            continue
        report.matched += 1
        if reply.kind == AUTO_REPLY:
            # An out-of-office is a machine, not a person. Stopping the sequence
            # on one would silently drop prospects who were simply on holiday.
            sub.fields["last_auto_reply"] = reply.snippet[:120].replace("\n", " ")
            continue
        if reply.opted_out:
            sub.status = UNSUBSCRIBED
            report.opted_out += 1
        elif sub.status not in (UNSUBSCRIBED,):
            sub.status = REPLIED
            if reply.kind in (INTERESTED, QUESTION):
                report.interested += 1
        sub.fields["last_reply"] = reply.snippet[:200].replace("\n", " ")
        sub.fields["replied_at"] = reply.received
        sub.fields["reply_kind"] = reply.kind
    return report


def check(settings: ImapSettings, subscribers: SubscriberList,
          log_path: str | Path, since_days: int = 30) -> InboxReport:
    """Read the inbox and update the list. The one call the CLI needs."""
    ids, addresses = sent_message_ids(log_path)
    addresses |= {s.email for s in subscribers.all()}
    replies = fetch_replies(settings, since_days, ids, addresses)
    return reconcile(subscribers, replies)
