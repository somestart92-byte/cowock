"""The screen you actually work from: who replied, who is pending, what's next.

Everything else in this package is a command line. This renders the same state
as a single HTML file you open in a browser — because the person running an
outreach campaign wants to read their replies, not parse a JSONL log.
"""

from __future__ import annotations

import datetime as _dt
import html
import json
from collections import Counter
from pathlib import Path

from .email_list import BOUNCED, REPLIED, SUBSCRIBED, UNSUBSCRIBED, SubscriberList


def _load_log(path: str | Path) -> list[dict]:
    path = Path(path)
    if not path.exists():
        return []
    rows: list[dict] = []
    with path.open("r", encoding="utf-8") as fh:
        for line in fh:
            try:
                rows.append(json.loads(line))
            except json.JSONDecodeError:
                continue
    return rows


_CSS = """
:root{--bg:#EFF2F1;--card:#fff;--ink:#16211F;--dim:#5E6E69;--line:#D2DAD7;
--go:#0E7A5F;--go-bg:#DCEBE5;--stop:#A8442A;--stop-bg:#F3E2DB;--wait:#8A6D1F;--wait-bg:#F5EBD3;}
@media(prefers-color-scheme:dark){:root{--bg:#0F1614;--card:#18211E;--ink:#E7EDEB;
--dim:#93A29C;--line:#2A3532;--go:#46B694;--go-bg:#14312A;--stop:#DB8465;--stop-bg:#332019;
--wait:#D8B86A;--wait-bg:#312813;}}
*{box-sizing:border-box}
body{margin:0;background:var(--bg);color:var(--ink);font:16px/1.6 -apple-system,Segoe UI,Helvetica,Arial,sans-serif;}
.wrap{max-width:960px;margin:0 auto;padding:32px 20px 64px}
h1{font-size:1.9rem;margin:0 0 4px;letter-spacing:-.02em}
.sub{color:var(--dim);margin:0 0 28px;font-size:.95rem}
h2{font-size:1.1rem;margin:36px 0 12px;letter-spacing:-.01em}
.tiles{display:grid;grid-template-columns:repeat(auto-fit,minmax(130px,1fr));gap:12px}
.tile{background:var(--card);border:1px solid var(--line);border-radius:4px;padding:16px}
.tile .n{font-size:1.9rem;font-weight:700;line-height:1;font-variant-numeric:tabular-nums}
.tile .l{color:var(--dim);font-size:.76rem;text-transform:uppercase;letter-spacing:.08em;margin-top:6px}
.tile.go .n{color:var(--go)} .tile.stop .n{color:var(--stop)} .tile.wait .n{color:var(--wait)}
.reply{background:var(--card);border:1px solid var(--line);border-left:3px solid var(--go);
border-radius:0 4px 4px 0;padding:16px 18px;margin-bottom:10px}
.reply .who{font-weight:600} .reply .meta{color:var(--dim);font-size:.82rem;margin:2px 0 8px}
.reply .body{white-space:pre-wrap;font-size:.95rem}
.scroll{overflow-x:auto;background:var(--card);border:1px solid var(--line);border-radius:4px}
table{border-collapse:collapse;width:100%;font-size:.88rem}
th,td{text-align:left;padding:10px 14px;border-bottom:1px solid var(--line);white-space:nowrap}
th{color:var(--dim);font-size:.7rem;text-transform:uppercase;letter-spacing:.07em}
tr:last-child td{border-bottom:none}
.pill{font-size:.7rem;padding:3px 8px;border-radius:2px;text-transform:uppercase;letter-spacing:.05em}
.pill.go{background:var(--go-bg);color:var(--go)}
.pill.stop{background:var(--stop-bg);color:var(--stop)}
.pill.wait{background:var(--wait-bg);color:var(--wait)}
.empty{color:var(--dim);background:var(--card);border:1px dashed var(--line);
border-radius:4px;padding:22px;text-align:center}
"""

_PILL = {SUBSCRIBED: "wait", REPLIED: "go", UNSUBSCRIBED: "stop", BOUNCED: "stop"}
_KIND_LABEL = {"interested": "interested", "question": "asked a question",
               "not_interested": "not interested", "auto_reply": "auto-reply",
               "unclear": "replied"}
_LABEL = {SUBSCRIBED: "not yet replied", REPLIED: "replied", UNSUBSCRIBED: "opted out",
          BOUNCED: "bounced"}


def render(subscribers: SubscriberList, log_path: str | Path,
           campaign_name: str = "Outreach") -> str:
    """Build the dashboard HTML from the list and the send log."""
    log = _load_log(log_path)
    sent = [r for r in log if r.get("status") == "sent"]
    people = subscribers.all()
    counts = Counter(s.status for s in people)
    sent_to = {r.get("email", "").lower() for r in sent}
    replies = [s for s in people if s.status == REPLIED]
    hot = [s for s in replies if s.fields.get("reply_kind") in ("interested", "question")]

    reply_rate = f"{len(replies) / len(sent_to) * 100:.0f}%" if sent_to else "—"

    tiles = [
        ("go", len(hot), "worth calling"),
        ("go", len(replies), "replied"),
        ("", len(sent_to), "people emailed"),
        ("", len(sent), "emails sent"),
        ("wait", counts.get(SUBSCRIBED, 0), "still pending"),
        ("stop", counts.get(UNSUBSCRIBED, 0), "opted out"),
        ("", reply_rate, "reply rate"),
    ]
    tile_html = "".join(
        f'<div class="tile {cls}"><div class="n">{html.escape(str(n))}</div>'
        f'<div class="l">{html.escape(label)}</div></div>'
        for cls, n, label in tiles
    )

    if replies:
        reply_html = "".join(
            f'<div class="reply"><div class="who">{html.escape(s.name or s.email)}</div>'
            f'<div class="meta">{html.escape(s.fields.get("company", ""))} &middot; '
            f'{html.escape(s.email)} &middot; {html.escape(s.fields.get("replied_at", ""))}</div>'
            f'<div class="body">{html.escape(s.fields.get("last_reply", "(no preview)"))}</div></div>'
            for s in replies
        )
    else:
        reply_html = ('<div class="empty">No replies yet. Run <b>email inbox</b> '
                      'after sending to pull them in.</div>')

    rows = []
    for s in people:
        times = sum(1 for r in sent if r.get("email", "").lower() == s.email)
        rows.append(
            f"<tr><td>{html.escape(s.name or '—')}</td>"
            f"<td>{html.escape(s.fields.get('company', '—'))}</td>"
            f"<td>{html.escape(s.fields.get('trade', '—'))}</td>"
            f"<td>{html.escape(s.email)}</td>"
            f"<td><span class='pill {_PILL.get(s.status, 'wait')}'>"
            f"{html.escape(_LABEL.get(s.status, s.status))}</span></td>"
            f"<td>{times}</td></tr>"
        )
    table = ("<div class='scroll'><table><thead><tr><th>Name</th><th>Company</th>"
             "<th>Trade</th><th>Email</th><th>Status</th><th>Emails sent</th></tr></thead>"
             f"<tbody>{''.join(rows)}</tbody></table></div>"
             ) if rows else "<div class='empty'>No prospects loaded yet.</div>"

    stamp = _dt.datetime.now().strftime("%d %b %Y, %H:%M")
    return f"""<!doctype html>
<html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>{html.escape(campaign_name)} — inbox</title><style>{_CSS}</style></head>
<body><div class="wrap">
<h1>{html.escape(campaign_name)}</h1>
<p class="sub">Updated {stamp}. Anyone who replies stops receiving the sequence automatically.</p>
<div class="tiles">{tile_html}</div>
<h2>Replies</h2>
{reply_html}
<h2>Everyone</h2>
{table}
</div></body></html>
"""


def write(subscribers: SubscriberList, log_path: str | Path, out_path: str | Path,
          campaign_name: str = "Outreach") -> Path:
    out = Path(out_path)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(render(subscribers, log_path, campaign_name), encoding="utf-8")
    return out
