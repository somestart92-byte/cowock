# Northbound Copy

**Conversion copywriting for B2B SaaS** — email sequences, landing pages, and lifecycle/onboarding copy that turns trials into paying customers.

> Words that move users to act.

This repository is the operating system for the business: brand, plan, pricing, a deployable website, and a ready-to-send outreach kit.

## What's here

| Path | What it is |
|------|------------|
| [`docs/brand-foundation.md`](docs/brand-foundation.md) | Name options, positioning, brand voice, value proposition, elevator pitch |
| [`docs/business-plan.md`](docs/business-plan.md) | Target market, services, 90-day launch roadmap, revenue model, goals |
| [`docs/pricing.md`](docs/pricing.md) | Service packages, project rates, and monthly retainers |
| [`docs/outreach/cold-email-templates.md`](docs/outreach/cold-email-templates.md) | Cold email + LinkedIn + follow-up templates |
| [`docs/outreach/portfolio-samples.md`](docs/outreach/portfolio-samples.md) | Spec/sample copy pieces to show before you have clients |
| [`docs/outreach/social-posts.md`](docs/outreach/social-posts.md) | 14 ready-to-schedule social posts (LinkedIn/X) |
| [`site/index.html`](site/index.html) | The landing page (static, deployable to GitHub Pages) |

## The website

`site/` is a self-contained static site — no build step, no dependencies.

**Preview locally:**
```bash
cd site && python3 -m http.server 8000
# open http://localhost:8000
```

**Deploy free on GitHub Pages:** Settings → Pages → Build from branch → select this branch, folder `/site` (or move `site/*` to repo root / `/docs`). Then point your domain at it.

## First 7 days (do this)

1. Read `docs/brand-foundation.md` and lock the business name + your contact email.
2. Set pricing from `docs/pricing.md` — pick your starting numbers.
3. Build 2 portfolio samples from `docs/outreach/portfolio-samples.md`.
4. Update the email/links in `site/index.html`, then deploy it.
5. Send 10 cold emails/day using `docs/outreach/cold-email-templates.md`.
6. Schedule the social posts from `docs/outreach/social-posts.md`.
7. Track replies and book calls.

The goal of month one: **2 paying clients or 1 retainer.**
