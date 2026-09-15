"""Email campaigns: write the sequence, merge in the reader, render text + HTML.

A campaign is a list of emails with a drip delay. Three shapes cover almost
everything a small digital-products business needs:

    welcome    — what a new subscriber gets, starting the day they join
    launch     — the sequence around a product going live
    nurture    — ongoing value emails that keep the list warm
    broadcast  — a single one-off email

Copy is written under the same honesty rules as the rest of cowock: the subject
line must describe what is actually inside, no false scarcity, no income or
results claims. Everything still goes through compliance.review() and your
approval before a single message leaves the machine.
"""

from __future__ import annotations

import html as _html
import json
import re
from dataclasses import dataclass, field

from .llm import LLM

KINDS = ("welcome", "launch", "nurture", "broadcast")

_DEFAULT_COUNT = {"welcome": 3, "launch": 3, "nurture": 2, "broadcast": 1}
_DEFAULT_DELAYS = {"welcome": [0, 2, 5], "launch": [0, 2, 4], "nurture": [0, 7], "broadcast": [0]}

_SHAPE = {
    "welcome": (
        "A welcome sequence for someone who just joined the list. Email 1 delivers "
        "what they signed up for and sets expectations; email 2 gives a genuinely "
        "useful standalone tip; email 3 introduces the paid product as an optional "
        "next step, without pressure."
    ),
    "launch": (
        "A launch sequence for a product that is now available. Email 1 announces it "
        "and explains exactly who it is for; email 2 goes deep on one concrete problem "
        "it solves; email 3 is a short, calm last note for people who meant to look."
    ),
    "nurture": (
        "Value-first emails for an existing list. Each one must be useful on its own "
        "even if the reader never buys anything. Mention the product only in passing."
    ),
    "broadcast": ("One standalone email with a single clear purpose and one call to action."),
}


def slugify(text: str) -> str:
    s = re.sub(r"[^a-z0-9]+", "-", (text or "").lower()).strip("-")
    return s[:60] or "campaign"


# --------------------------------------------------------------------- merge

_FIELD_RE = re.compile(r"\{\{\s*([a-zA-Z0-9_]+)\s*\}\}")


def merge_fields(text: str) -> list[str]:
    """Every {{field}} referenced in a piece of copy."""
    return sorted(set(_FIELD_RE.findall(text or "")))


def render_fields(text: str, ctx: dict[str, str]) -> str:
    """Substitute {{field}} from ctx. Unknown fields render empty, never raw.

    A stray '{{first_name}}' arriving in a customer's inbox is the classic
    amateur-hour email bug, so anything unmatched is dropped instead of shipped.
    """
    def _sub(match: re.Match[str]) -> str:
        return str(ctx.get(match.group(1), "") or "")

    out = _FIELD_RE.sub(_sub, text or "")
    # Collapse the double spaces / stray commas a missing name leaves behind.
    out = re.sub(r"[ \t]{2,}", " ", out)
    out = re.sub(r"(?m)^([^\S\n]*)(Hi|Hello|Assalamu alaikum|Salam)\s*,", r"\1\2,", out)
    return out


# ------------------------------------------------------------------ markdown

def markdown_to_html(md: str) -> str:
    """A deliberately small Markdown subset — enough for email, no dependency.

    Supports headings, bold, italic, links, bullet lists and paragraphs. Email
    clients ignore most of everything else anyway.
    """
    def inline(text: str) -> str:
        text = _html.escape(text, quote=False)
        text = re.sub(r"\[([^\]]+)\]\(([^)\s]+)\)", r'<a href="\2">\1</a>', text)
        text = re.sub(r"\*\*([^*]+)\*\*", r"<strong>\1</strong>", text)
        text = re.sub(r"(?<!\*)\*([^*\n]+)\*(?!\*)", r"<em>\1</em>", text)
        return text

    blocks: list[str] = []
    buffer: list[str] = []
    list_items: list[str] = []

    def flush_paragraph() -> None:
        if buffer:
            blocks.append("<p>" + inline(" ".join(buffer)) + "</p>")
            buffer.clear()

    def flush_list() -> None:
        if list_items:
            items = "".join(f"<li>{inline(i)}</li>" for i in list_items)
            blocks.append(f"<ul>{items}</ul>")
            list_items.clear()

    for line in (md or "").splitlines():
        stripped = line.strip()
        if not stripped:
            flush_paragraph()
            flush_list()
            continue
        heading = re.match(r"^(#{1,4})\s+(.*)$", stripped)
        if heading:
            flush_paragraph()
            flush_list()
            level = min(len(heading.group(1)) + 1, 4)  # h1 is the email subject
            blocks.append(f"<h{level}>{inline(heading.group(2))}</h{level}>")
            continue
        if re.match(r"^[-*+]\s+", stripped):
            flush_paragraph()
            list_items.append(re.sub(r"^[-*+]\s+", "", stripped))
            continue
        if stripped in ("---", "***", "___"):
            flush_paragraph()
            flush_list()
            blocks.append("<hr>")
            continue
        flush_list()
        buffer.append(stripped)

    flush_paragraph()
    flush_list()
    return "\n".join(blocks)


_HTML_SHELL = """\
<!doctype html>
<html><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>{subject}</title></head>
<body style="margin:0;padding:0;background:#f4f4f5;">
<div style="display:none;max-height:0;overflow:hidden;opacity:0;">{preheader}</div>
<table role="presentation" width="100%" cellpadding="0" cellspacing="0" style="background:#f4f4f5;">
<tr><td align="center" style="padding:24px 12px;">
<table role="presentation" width="100%" cellpadding="0" cellspacing="0" style="max-width:600px;background:#ffffff;border-radius:8px;">
<tr><td style="padding:32px 28px;font-family:-apple-system,Segoe UI,Helvetica,Arial,sans-serif;font-size:16px;line-height:1.6;color:#1f2933;">
{body}
{cta}
</td></tr>
<tr><td style="padding:0 28px 28px;font-family:-apple-system,Segoe UI,Helvetica,Arial,sans-serif;font-size:12px;line-height:1.6;color:#6b7280;">
<hr style="border:none;border-top:1px solid #e5e7eb;margin:0 0 16px;">
{footer}
</td></tr>
</table></td></tr></table></body></html>
"""

_CTA = (
    '<p style="margin:28px 0 0;"><a href="{url}" '
    'style="background:#0f766e;color:#ffffff;text-decoration:none;padding:12px 22px;'
    'border-radius:6px;display:inline-block;font-weight:600;">{label}</a></p>'
)


# -------------------------------------------------------------------- models

@dataclass
class Email:
    subject: str
    preheader: str = ""
    body_markdown: str = ""
    cta_label: str = ""
    cta_url: str = ""
    delay_days: int = 0

    def to_dict(self) -> dict:
        return {
            "subject": self.subject,
            "preheader": self.preheader,
            "body_markdown": self.body_markdown,
            "cta_label": self.cta_label,
            "cta_url": self.cta_url,
            "delay_days": self.delay_days,
        }

    @classmethod
    def from_dict(cls, data: dict) -> "Email":
        return cls(
            subject=str(data.get("subject", "")).strip(),
            preheader=str(data.get("preheader", "")).strip(),
            body_markdown=str(data.get("body_markdown", data.get("body", ""))),
            cta_label=str(data.get("cta_label", "")).strip(),
            cta_url=str(data.get("cta_url", "")).strip(),
            delay_days=int(data.get("delay_days", 0) or 0),
        )

    def merge_fields(self) -> list[str]:
        joined = " ".join([self.subject, self.preheader, self.body_markdown, self.cta_url])
        return merge_fields(joined)

    # -------------------------------------------------------------- render

    def rendered_cta(self, ctx: dict[str, str]) -> tuple[str, str]:
        """The button, or ('', '') — a CTA whose link is empty is not shipped."""
        if not (self.cta_label and self.cta_url):
            return "", ""
        url = render_fields(self.cta_url, ctx).strip()
        if not url:
            return "", ""
        return render_fields(self.cta_label, ctx).strip() or "Read more", url

    def render_subject(self, ctx: dict[str, str]) -> str:
        return render_fields(self.subject, ctx).strip()

    def render_text(self, ctx: dict[str, str], footer: str = "") -> str:
        body = render_fields(self.body_markdown, ctx).strip()
        parts = [body]
        label, url = self.rendered_cta(ctx)
        if url:
            parts.append(f"{label}: {url}")
        if footer:
            parts.append("-- \n" + footer)
        return "\n\n".join(p for p in parts if p).strip() + "\n"

    def render_html(self, ctx: dict[str, str], footer: str = "") -> str:
        body = markdown_to_html(render_fields(self.body_markdown, ctx))
        label, url = self.rendered_cta(ctx)
        cta = ""
        if url:
            cta = _CTA.format(url=_html.escape(url, quote=True),
                              label=_html.escape(label, quote=False))
        footer_html = markdown_to_html(footer) if footer else ""
        return _HTML_SHELL.format(
            subject=_html.escape(self.render_subject(ctx), quote=False),
            preheader=_html.escape(render_fields(self.preheader, ctx), quote=False),
            body=body,
            cta=cta,
            footer=footer_html,
        )


@dataclass
class Campaign:
    name: str
    kind: str
    slug: str = ""
    emails: list[Email] = field(default_factory=list)
    product_title: str = ""
    product_url: str = ""
    price_usd: float = 0.0
    audience_tag: str = ""
    created: str = ""

    def __post_init__(self) -> None:
        if not self.slug:
            self.slug = slugify(self.name)

    def to_dict(self) -> dict:
        return {
            "name": self.name,
            "kind": self.kind,
            "slug": self.slug,
            "product_title": self.product_title,
            "product_url": self.product_url,
            "price_usd": self.price_usd,
            "audience_tag": self.audience_tag,
            "created": self.created,
            "emails": [e.to_dict() for e in self.emails],
        }

    @classmethod
    def from_dict(cls, data: dict) -> "Campaign":
        return cls(
            name=data.get("name", "Untitled campaign"),
            kind=data.get("kind", "broadcast"),
            slug=data.get("slug", ""),
            emails=[Email.from_dict(e) for e in data.get("emails", [])],
            product_title=data.get("product_title", ""),
            product_url=data.get("product_url", ""),
            price_usd=float(data.get("price_usd", 0) or 0),
            audience_tag=data.get("audience_tag", ""),
            created=data.get("created", ""),
        )

    def combined_text(self) -> str:
        """Everything a compliance reviewer needs to read."""
        chunks: list[str] = [self.name]
        for mail in self.emails:
            chunks += [mail.subject, mail.preheader, mail.body_markdown, mail.cta_label]
        return "\n\n".join(c for c in chunks if c)

    def to_markdown(self) -> str:
        lines = [f"# Email campaign — {self.name}\n", f"**Kind:** {self.kind}"]
        if self.product_title:
            lines.append(f"**Product:** {self.product_title}"
                         + (f" (${self.price_usd:.0f})" if self.price_usd else ""))
        if self.audience_tag:
            lines.append(f"**Audience tag:** `{self.audience_tag}`")
        lines.append("")
        for i, mail in enumerate(self.emails):
            when = "on signup" if mail.delay_days == 0 else f"day {mail.delay_days}"
            lines.append(f"## Email {i + 1} — {when}\n")
            lines.append(f"**Subject:** {mail.subject}")
            if mail.preheader:
                lines.append(f"**Preheader:** {mail.preheader}")
            lines.append("")
            lines.append(mail.body_markdown.strip())
            if mail.cta_label and mail.cta_url:
                lines.append(f"\n**CTA:** [{mail.cta_label}]({mail.cta_url})")
            lines.append("")
        return "\n".join(lines) + "\n"


# --------------------------------------------------------------------- build

def _fallback_emails(kind: str, product_title: str, count: int) -> list[Email]:
    """Structurally real emails for DRY-RUN, clearly labelled as placeholders."""
    delays = _DEFAULT_DELAYS.get(kind, [0, 2, 5])
    product = product_title or "the guide"
    emails: list[Email] = []
    for i in range(count):
        emails.append(
            Email(
                subject=f"[DRY-RUN] {kind.title()} email {i + 1}: {product}",
                preheader="Placeholder preheader — no ANTHROPIC_API_KEY set.",
                body_markdown=(
                    "Hi {{first_name}},\n\n"
                    f"This is placeholder copy for {kind} email {i + 1}. The sequence "
                    "structure, merge fields, rendering, compliance review, approval "
                    "gate and sending all work — only the words are mocked.\n\n"
                    "Set `ANTHROPIC_API_KEY` and re-run to write the real copy.\n\n"
                    "— {{sender_name}}"
                ),
                cta_label="See the guide",
                cta_url="{{product_url}}",
                delay_days=delays[i] if i < len(delays) else delays[-1] + 3 * (i - len(delays) + 1),
            )
        )
    return emails


def build_campaign(
    kind: str,
    brand: dict,
    llm: LLM,
    product: dict | None = None,
    count: int | None = None,
    notes: str = "",
    audience_tag: str = "",
) -> Campaign:
    """Write a campaign. Falls back to labelled placeholders in DRY-RUN."""
    if kind not in KINDS:
        raise ValueError(f"unknown campaign kind {kind!r}; expected one of {', '.join(KINDS)}")

    product = product or {}
    title = str(product.get("title", "")).strip()
    subtitle = str(product.get("subtitle", "")).strip()
    price = float(product.get("price_usd", 0) or 0)
    count = count or _DEFAULT_COUNT.get(kind, 3)
    name = f"{kind.title()} — {title}" if title else f"{kind.title()} campaign"

    campaign = Campaign(
        name=name,
        kind=kind,
        emails=[],
        product_title=title,
        price_usd=price,
        audience_tag=audience_tag,
        created="",
    )

    if llm.dry_run:
        campaign.emails = _fallback_emails(kind, title, count)
        return campaign

    brand_name = str(brand.get("name", "")).strip()
    system = (
        f"You write email marketing for {brand_name or 'a halal brand'}. Rules you "
        "never break: the subject line must honestly describe what is inside; no "
        "false scarcity or fake deadlines; no income, earnings, or guaranteed-result "
        "claims; no exaggeration ('can' and 'could', never 'will' or 'guaranteed'); "
        "no invented statistics — if a number was not measured, do not print it; "
        "respectful of Islamic etiquette. Write like one person emailing another — "
        "short paragraphs, plain words, one clear call to action per email."
    )
    product_block = (
        f"Product: {title} — {subtitle} (${price:.0f})\n" if title else "No product yet.\n"
    )
    notes_block = f"\nContext to use:\n{notes}\n" if notes else ""
    prompt = (
        f"Brand voice: {brand.get('voice', 'warm, practical')}\n"
        f"Audience: {brand.get('audience', 'readers who opted in')}\n"
        f"{product_block}{notes_block}\n"
        f"Write {count} email(s) for this sequence.\n{_SHAPE.get(kind, '')}\n\n"
        "Personalize with the merge fields {{first_name}} and {{sender_name}} only; "
        "use {{product_url}} for the product link. Do NOT invent any other merge "
        "field, and do NOT write an unsubscribe footer — one is added automatically.\n\n"
        "Body should be 120-250 words of Markdown. Respond ONLY with JSON:\n"
        '{"emails": [{"subject": str, "preheader": str, "body_markdown": str, '
        '"cta_label": str, "cta_url": str, "delay_days": number}]}'
    )
    raw = llm.complete(system, prompt, temperature=0.7)
    try:
        start, end = raw.find("{"), raw.rfind("}")
        data = json.loads(raw[start : end + 1])
        emails = [Email.from_dict(e) for e in data.get("emails", [])]
        campaign.emails = [e for e in emails if e.subject and e.body_markdown][:count]
    except Exception:
        campaign.emails = []

    if not campaign.emails:  # model returned something unusable
        campaign.emails = _fallback_emails(kind, title, count)
    for i, mail in enumerate(campaign.emails):
        if mail.delay_days == 0 and i > 0:
            defaults = _DEFAULT_DELAYS.get(kind, [0, 2, 5])
            mail.delay_days = defaults[i] if i < len(defaults) else i * 3
    return campaign
