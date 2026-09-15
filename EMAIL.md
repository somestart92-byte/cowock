# Email Marketing — write the campaign, own the list, send it yourself

Social posts rent an audience. An email list is the one asset you own outright,
and for digital products it is usually where the sales actually happen.

This module does three things:

| | |
|---|---|
| **Campaigns** | The agent writes welcome / launch / nurture / broadcast sequences |
| **The list** | A CSV you own — tags, consent, unsubscribes, no ESP subscription |
| **The sender** | Real delivery over *your* SMTP account, throttled and logged |

Nothing is ever sent without your explicit approval. The default send is a
**rehearsal** that writes `.eml` files to an outbox you can open and read.

---

## 1. Build a campaign

```bash
python -m src.main email build --kind welcome        # 3-email welcome sequence
python -m src.main email build --kind launch --url https://gumroad.com/l/your-product
python -m src.main email build --kind nurture --count 2
python -m src.main email build --kind broadcast --notes "Ramadan planner is 40% done"
```

It picks up your most recent product from `products/output/` automatically (or
pass `--product products/output/<run>`), writes the copy, runs the **same
halal-compliance review** as everything else in cowock, and stops:

```
emails/campaigns/<stamp>-<kind>-<slug>/
  campaign.json     # the machine-readable campaign
  campaign.md       # read this — it's the whole sequence, subject lines and all
  meta.json         # compliance verdict + warnings
approvals/email-<slug>.json     # set "approved": true to unlock a live send
```

Runs in DRY-RUN without `ANTHROPIC_API_KEY` — the structure, rendering,
compliance and sending all work; only the words are mocked.

## 2. Build the list

```bash
python -m src.main subscribers add amina@example.com --name "Amina" --tags moms,budget --source freebie
python -m src.main subscribers import my-export.csv --tags moms
python -m src.main subscribers unsubscribe --email amina@example.com
python -m src.main subscribers stats
```

The list lives at `emails/subscribers.csv` — **git-ignored on purpose**, because
it is other people's personal data. `emails/subscribers.example.csv` shows the
shape. Consent rules are enforced in code, not just in the docs:

- An unsubscribed person is **never** silently re-added; that takes an explicit
  `resubscribe=True`.
- Importing a CSV that marks someone unsubscribed keeps them unsubscribed.
- Every subscriber gets a stable token, so unsubscribe links never have to put
  an email address in a URL.
- `--source` records where each person opted in. If you can't name the source,
  you don't have consent to mail them.

## 3. Rehearse

```bash
python -m src.main email send --campaign <slug>
```

No `--live`, so nothing touches the network. Each message is written to
`emails/outbox/*.eml` — double-click one and it opens in your mail app exactly
as a subscriber would see it, personalization, HTML and all. Proofread there.

```bash
python -m src.main email send --campaign <slug> --test-to you@example.com --live   # just you
python -m src.main email send --campaign <slug> --backend console                  # names only
```

## 4. Send for real

Set credentials in `.env` (see `.env.example`) — any SMTP provider works. For
Gmail you need an **App Password**, not your normal password:

```bash
EMAIL_FROM=you@yourdomain.com
SMTP_HOST=smtp.gmail.com
SMTP_PORT=587
SMTP_USER=you@yourdomain.com
SMTP_PASSWORD=your-app-password
```

Fill in `unsubscribe_url` and `postal_address` in `config.yaml → email`, set
`"approved": true` in the approval file, then:

```bash
python -m src.main email send --campaign <slug> --live              # blast email 1
python -m src.main email send --campaign <slug> --live --index 1    # the second email
python -m src.main email send --campaign <slug> --live --drip       # each person gets what's due
python -m src.main email send --campaign <slug> --live --limit 25   # toe in the water
```

`--drip` is the autoresponder: it looks at each subscriber's join date against
the sequence's `delay_days` and sends only the emails they've earned. Run it on
a schedule (cron, or a Claude Code Routine) and your welcome sequence runs
itself.

## The gates before a live send

A live send is refused unless **all** of these hold — the error names whichever
one failed:

1. An approval file exists for the campaign and says `"approved": true`.
2. The compliance review passed.
3. `EMAIL_FROM`, `SMTP_HOST`, `SMTP_USER`, `SMTP_PASSWORD` are set.
4. `unsubscribe_url` (or `unsubscribe_mailto`) and `postal_address` are configured.

## What every message carries

- A **working unsubscribe link** plus `List-Unsubscribe` and
  `List-Unsubscribe-Post` headers, so Gmail and Apple Mail show a one-click
  unsubscribe button.
- Your **postal address** — CAN-SPAM requires it, and honesty about who is
  writing is the same rule the rest of cowock runs on.
- Both a **plain-text and an HTML** part, so it renders everywhere.
- Personalization via `{{first_name}}`, `{{name}}`, `{{sender_name}}`,
  `{{product_title}}`, `{{product_url}}`, `{{price}}`, `{{unsubscribe_url}}`.
  An unmatched field renders **empty rather than raw** — no subscriber ever
  receives a literal `{{first_name}}`.

## Safety rails in the sender

- **No double sends.** Every delivery is logged to `emails/send-log.jsonl`, and
  a `(campaign, email index, recipient)` that already went out is skipped. Re-run
  a crashed or double-fired send without mailing anyone twice.
- **Throttling.** `rate_limit_per_minute` (default 20) paces delivery;
  `daily_limit` (default 400) keeps you under consumer-SMTP caps.
- **Unsubscribed and bounced addresses are never sent to**, ever, by any path.
- **One bad address can't kill a run** — it is recorded as failed and the send
  continues.
- Every run writes `send-report-<stamp>.json` next to the campaign.

## Honest email, by design

The copywriter works under the same rules as the rest of cowock: the subject
line must describe what is actually inside, no false scarcity or invented
deadlines, no income or guaranteed-result claims, `can`/`could` rather than
`will`. Every campaign is reviewed against `config.yaml → halal_rules` before it
reaches your approval file.

## Tests

```bash
python tests/test_email.py      # 19 tests, no API key and no network needed
```
