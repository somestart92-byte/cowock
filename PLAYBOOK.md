# Publishing Playbook — driving cowock through Claude Code

Once `python -m src.main run` has produced an approved product, this is how the
agent takes it live using the tools already connected in your Claude Code
session. You stay in control: nothing here happens until you ask.

## One-time setup
1. **Payments/store:** create a halal-friendly store (e.g. Gumroad) and connect
   your bank. This is the part only you can do.
2. **Social:** connect your accounts in Buffer (`publish.buffer.com`).
3. **Email list:** have a sender address in Gmail.

## Per-product launch (just ask Claude)

> "Publish the latest approved cowock product."

The agent will then:

1. **Read the approval** — confirm `approved: true` in `approvals/<run>.json`.
   If not approved, it stops and asks you.
2. **Cover image — Canva**
   - `search-brand-templates` → pick a template
   - `create-brand-template-draft` using `cover_brief` from `marketing.md`
   - `publish-brand-template` → export the cover
3. **Host the product file — Google Drive**
   - `create_file` to upload `product.md` (or its exported PDF)
   - set a shareable link for delivery
4. **Social posts — Buffer**
   - `get_account` → org id, `list_channels` → channel ids
   - `create_post` (default `addToQueue`) for each channel in `marketing.md`
   - never guess channel ids — always use ones returned by `list_channels`
5. **Launch email — Gmail**
   - `create_draft` with the email from `marketing.md`
   - **left as a draft for you to send** (email blasts deserve a human send)
6. **Report back** — links to the queued posts, the draft, and the Drive file.

## Recurring / hands-off cadence

Tell Claude, e.g.:

> "Every Monday, generate one new product, run compliance, and queue the social
> posts to Buffer. Leave the email as a draft and the publish-to-store step for
> me."

You can also schedule this from cron by running `python -m src.main run` and
then having a session process new entries in `approvals/`.

## Guardrails (by design)
- Money movement and store publishing are **always** manual.
- Email sends are left as **drafts**.
- Anything failing the halal-compliance review is flagged and **not queued**.
- You can change the strictness in `config.yaml → halal_rules`.

> Note: compliance checks are software guidance, not a religious ruling.
> For binding questions, consult a qualified scholar.
