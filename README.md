# cowock — Halal Digital-Products Agent

An automation agent that **builds and markets halal digital products** for you.
It generates the product (ebook / checklist / planner), writes the marketing
(social posts + launch email + cover brief), and runs a **halal-compliance
review** on everything — then hands it to you for a one-click approval.

## The honest model: "without you involving" — within limits

No software can run a real business with *zero* human involvement. Money,
banking, business registration, and the final "publish" decision legally and
practically need you. So cowock is built to do **everything except the parts
only you can do**:

| The agent does | You do (rarely, fast) |
|---|---|
| Invent the product idea & pricing | Approve / tweak |
| Write the full product | Skim & approve |
| Write all marketing copy | Approve |
| Screen for halal compliance | Final judgement |
| Queue posts / drafts / uploads | Click publish |
| — | Connect payment + bank account (one time) |

Nothing is published and no money moves without your explicit yes. That's the
design, on purpose.

## Quick start

```bash
pip install -r requirements.txt          # PyYAML required; anthropic for live mode
cp .env.example .env                      # add ANTHROPIC_API_KEY for real content
python -m src.main run                    # generate a product + marketing kit
```

Runs with **no API key** in DRY-RUN mode (mocked text, real files & flow) so you
can see the whole pipeline first. Add `ANTHROPIC_API_KEY` to generate real,
sellable content with `claude-opus-4-8`.

### Output
```
products/output/<timestamp>-<title>/
  product.md      # the product itself
  marketing.md    # posts, email, cover brief
  meta.json       # pricing + compliance verdict
approvals/<...>.json   # set "approved": true to greenlight
```

## Configure your niche

Everything is driven by `config.yaml`. The one setting that matters most:

```yaml
niche: "Islamic productivity & habit-building for busy Muslim professionals"
```

Change it to your idea and re-run. Also set brand voice, product types,
channels, and the `halal_rules` the compliance reviewer enforces.

## How it works

```
config.yaml
   │
   ▼
 product.py   → idea + pricing + full written product
   │
   ▼
 marketing.py → social posts + email + cover brief
   │
   ▼
 compliance.py → keyword screen + LLM halal review
   │
   ▼
 pipeline.py  → writes artifacts + approval request   (STOPS here — your turn)
```

## Going live (publishing)

Two supported paths — see [`PLAYBOOK.md`](PLAYBOOK.md) for step-by-step:

1. **Through Claude Code (easiest):** the connected MCP tools publish for you —
   **Buffer** (social), **Canva** (covers), **Gmail** (launch email),
   **Google Drive** (host/deliver files). Just say *"publish the latest approved
   product."*
2. **Standalone/cron:** wire the product to a halal store (e.g. Gumroad) and
   Buffer's API for fully scheduled runs.

## Tests

```bash
python tests/test_pipeline.py     # or: pytest tests/
```

## What makes a digital-products business halal

- Sell a **beneficial product directly** (no riba/interest, no gambling).
- **Honest marketing** — no false scarcity or exaggerated guarantees.
- Halal **payment processing** (avoid interest-based features where possible).
- Content respects Islamic etiquette (`adab`). The reviewer enforces the rules
  in `config.yaml`; you have the final say. *This is software guidance, not a
  fatwa — consult a knowledgeable scholar for rulings.*
