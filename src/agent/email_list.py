"""Subscriber list — a plain CSV you own, no third-party ESP required.

Consent is the whole point: people are only ever added with a recorded source,
unsubscribes are permanent unless the person explicitly asks back in, and every
subscriber carries a stable token so a one-click unsubscribe link can identify
them without exposing their address in a URL.

The file is a normal CSV so you can open it in any spreadsheet, and export it
to a real ESP (Mailchimp/ConvertKit) the day you outgrow this.
"""

from __future__ import annotations

import csv
import datetime as _dt
import re
import secrets
from dataclasses import dataclass, field
from pathlib import Path

SUBSCRIBED = "subscribed"
UNSUBSCRIBED = "unsubscribed"
BOUNCED = "bounced"

FIELDS = ["email", "name", "status", "tags", "source", "joined", "token"]

# Anything else in the CSV — company, city, trade — rides along as a merge
# field. Cold outreach lives or dies on "{{company}}", so the list has to carry
# whatever columns your prospect export happens to have.

# Deliberately permissive: catches typos and junk, not exotic-but-valid addresses.
_EMAIL_RE = re.compile(r"^[^@\s,;]+@[^@\s,;]+\.[A-Za-z]{2,}$")


def is_valid_email(address: str) -> bool:
    return bool(_EMAIL_RE.match((address or "").strip()))


def _today() -> str:
    return _dt.date.today().isoformat()


@dataclass
class Subscriber:
    email: str
    name: str = ""
    status: str = SUBSCRIBED
    tags: list[str] = field(default_factory=list)
    source: str = ""
    joined: str = field(default_factory=_today)
    token: str = ""
    fields: dict[str, str] = field(default_factory=dict)  # extra CSV columns

    def __post_init__(self) -> None:
        self.email = self.email.strip().lower()
        if not self.token:
            self.token = secrets.token_urlsafe(16)

    @property
    def first_name(self) -> str:
        return self.name.strip().split(" ")[0] if self.name.strip() else ""

    @property
    def active(self) -> bool:
        return self.status == SUBSCRIBED

    def has_tag(self, tag: str) -> bool:
        return tag.strip().lower() in [t.strip().lower() for t in self.tags]

    def joined_date(self) -> _dt.date:
        try:
            return _dt.date.fromisoformat(self.joined)
        except ValueError:
            return _dt.date.today()

    def to_row(self) -> dict[str, str]:
        row = dict(self.fields)
        row.update({
            "email": self.email,
            "name": self.name,
            "status": self.status,
            "tags": "|".join(self.tags),
            "source": self.source,
            "joined": self.joined,
            "token": self.token,
        })
        return row

    @classmethod
    def from_row(cls, row: dict[str, str]) -> "Subscriber":
        raw_tags = (row.get("tags") or "").strip()
        return cls(
            email=row.get("email", ""),
            name=row.get("name", "") or "",
            status=(row.get("status") or SUBSCRIBED).strip() or SUBSCRIBED,
            tags=[t for t in raw_tags.split("|") if t],
            source=row.get("source", "") or "",
            joined=(row.get("joined") or _today()).strip() or _today(),
            token=(row.get("token") or "").strip(),
            fields={k: (v or "").strip() for k, v in row.items()
                    if k and k not in FIELDS and (v or "").strip()},
        )


class SubscriberList:
    """A consent-respecting mailing list stored as CSV."""

    def __init__(self, path: Path, subscribers: list[Subscriber] | None = None):
        self.path = Path(path)
        self._by_email: dict[str, Subscriber] = {}
        for sub in subscribers or []:
            self._by_email[sub.email] = sub

    # ---------------------------------------------------------------- io

    @classmethod
    def load(cls, path: str | Path) -> "SubscriberList":
        path = Path(path)
        if not path.exists():
            return cls(path)
        with path.open("r", encoding="utf-8", newline="") as fh:
            rows = list(csv.DictReader(fh))
        subs = [Subscriber.from_row(r) for r in rows if (r.get("email") or "").strip()]
        return cls(path, subs)

    def save(self) -> Path:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        extra: list[str] = []
        for sub in self._by_email.values():
            for key in sub.fields:
                if key not in extra:
                    extra.append(key)
        with self.path.open("w", encoding="utf-8", newline="") as fh:
            writer = csv.DictWriter(fh, fieldnames=FIELDS + extra)
            writer.writeheader()
            for sub in sorted(self._by_email.values(), key=lambda s: s.email):
                writer.writerow(sub.to_row())
        return self.path

    # ------------------------------------------------------------ mutate

    def add(
        self,
        email: str,
        name: str = "",
        tags: list[str] | None = None,
        source: str = "",
        resubscribe: bool = False,
    ) -> tuple[Subscriber, bool]:
        """Add or update a subscriber. Returns (subscriber, created).

        An unsubscribed person is NOT silently re-added — that is what makes a
        list a spam list. Pass resubscribe=True only when they asked back in.
        """
        if not is_valid_email(email):
            raise ValueError(f"not a valid email address: {email!r}")
        key = email.strip().lower()
        existing = self._by_email.get(key)
        if existing is None:
            sub = Subscriber(email=key, name=name, tags=list(tags or []), source=source)
            self._by_email[key] = sub
            return sub, True

        if name and not existing.name:
            existing.name = name
        for tag in tags or []:
            if not existing.has_tag(tag):
                existing.tags.append(tag)
        if source and not existing.source:
            existing.source = source
        if existing.status != SUBSCRIBED and resubscribe:
            existing.status = SUBSCRIBED
        return existing, False

    def unsubscribe(self, email: str = "", token: str = "") -> Subscriber | None:
        sub = self.get(email) if email else self.by_token(token)
        if sub is None:
            return None
        sub.status = UNSUBSCRIBED
        return sub

    def mark_bounced(self, email: str) -> Subscriber | None:
        sub = self.get(email)
        if sub is not None:
            sub.status = BOUNCED
        return sub

    def import_csv(self, path: str | Path, source: str = "import",
                   tags: list[str] | None = None) -> dict[str, int]:
        """Merge another CSV in. Accepts 'email' plus optional 'name'/'tags'."""
        added = updated = skipped = 0
        with Path(path).open("r", encoding="utf-8", newline="") as fh:
            for row in csv.DictReader(fh):
                address = (row.get("email") or row.get("Email") or "").strip()
                if not is_valid_email(address):
                    skipped += 1
                    continue
                row_tags = [t for t in (row.get("tags") or "").split("|") if t]
                sub, created = self.add(
                    address,
                    name=(row.get("name") or row.get("Name") or "").strip(),
                    tags=list(tags or []) + row_tags,
                    source=(row.get("source") or "").strip() or source,
                )
                # An import must never resurrect someone who opted out, and a
                # file that already carries a token keeps it so unsubscribe
                # links from earlier sends stay valid.
                row_status = (row.get("status") or "").strip().lower()
                if row_status in (UNSUBSCRIBED, BOUNCED):
                    sub.status = row_status
                if created and (row.get("token") or "").strip():
                    sub.token = row["token"].strip()
                if created and (row.get("joined") or "").strip():
                    sub.joined = row["joined"].strip()
                for key, value in row.items():
                    if key and key not in FIELDS and (value or "").strip():
                        sub.fields.setdefault(key, value.strip())
                added += int(created)
                updated += int(not created)
        return {"added": added, "updated": updated, "skipped": skipped}

    # ------------------------------------------------------------- query

    def get(self, email: str) -> Subscriber | None:
        return self._by_email.get((email or "").strip().lower())

    def by_token(self, token: str) -> Subscriber | None:
        token = (token or "").strip()
        if not token:
            return None
        for sub in self._by_email.values():
            if sub.token == token:
                return sub
        return None

    def all(self) -> list[Subscriber]:
        return sorted(self._by_email.values(), key=lambda s: s.email)

    def active(self, tag: str = "") -> list[Subscriber]:
        subs = [s for s in self.all() if s.active]
        if tag:
            subs = [s for s in subs if s.has_tag(tag)]
        return subs

    def stats(self) -> dict[str, int]:
        counts = {"total": len(self._by_email), SUBSCRIBED: 0, UNSUBSCRIBED: 0, BOUNCED: 0}
        for sub in self._by_email.values():
            counts[sub.status] = counts.get(sub.status, 0) + 1
        return counts

    def __len__(self) -> int:
        return len(self._by_email)
