# Sara AI — Project Memory (read this first)

This file is the running memory for the Sara AI outreach business. A new chat
should read this to pick up exactly where we left off.

## What this is
A fully-automated B2B outreach business selling **Sara**, an AI voice receptionist
for UK dental clinics. Landing page / live demo:
**https://wonderful-meerkat-938250.netlify.app/**
Goal: close paying clients. Near-term target the owner set: 2 closes, fast.

## The owner
- Name to sign outreach as: **Jordan** (use this in every email signature).
- Sender Gmail: voiceaifrin1@gmail.com (also somestart92@gmail.com).
- Wants 100% hands-off automation, hates manual steps, dislikes being asked
  lots of questions — bias toward just doing it.

## Hard rules (do not break)
- **Halal / 100% truthful.** No invented stats, no fake testimonials, no
  fabricated clinic-specific numbers. Only claim what Sara actually does.
- **Write like a person, not AI.** No bullet points in emails, no buzzwords,
  no "leverage/seamless/revolutionise". Open with THEIR problem.
- **Don't lead with the word "AI."** Mention it's automated once, plainly.
- Max 2 emails per clinic ever (1 initial + 1 follow-up).
- Opt-out (reply STOP) honoured instantly and permanently.
- Corporate mailboxes only (info@/reception@/hello@/dental@) — skip personal
  firstname.lastname@.

## Targeting (the qualified lead profile)
- UK dental clinics, **independently owned** (NOT chains: skip Bupa, mydentist,
  Rodericks/Street Lane, Portman/PortmanDentex, Colosseum, Whitecross, Dental
  Care Alliance).
- **England, Wales, Northern Ireland only — Scotland EXCLUDED** (Edinburgh,
  Glasgow, Aberdeen, Dundee, etc.). Enforced in scripts/daily-outreach.js.
- Buying signal: clinic is **actively hiring a receptionist** (only use the
  "noticed you're hiring" / "before you hire" hook when verified true).
- Pitch: £299/month, one-off £999 setup, first month free.

## The pitch logic (see PROBLEM-ANALYSIS.md)
Clinics lose new patients at the phone — calls missed when the desk is busy or
after hours; callers don't leave voicemail, they ring the next dentist. Sara
answers every call, books into the diary, handles routine questions 24/7,
working ALONGSIDE the team (not replacing them). Sell the leak, not a statistic.

## Current state (as of 2026-06-27)
- **33 outreach drafts sit in the sender's Gmail Drafts**, all signed "Jordan",
  problem-first voice, demo link included. = 30 Leeds clinics + Green Apple
  (Oakham), One Dental (Peterborough), Stanley (Kidderminster).
- All tracked in **pipeline.csv** (single source of truth). Thread IDs there
  match the current Gmail drafts. Rows marked `draft-ready-guessed` use an
  `info@<domain>` email pattern (not verified-published) — small bounce risk.
- The owner still needs to: replace nothing (Jordan already in), open Gmail and
  **send** the drafts (verified ones first), then tell us when a reply lands.

## THE BLOCKER (most important next step)
Email sending is NOT automated yet. Gmail App Passwords are unavailable on the
account, so we switched the scripts to **Brevo SMTP** (free, 300/day, no 2FA).
To go fully hands-free the owner must:
1. Create a free account at app.brevo.com
2. Get SMTP login + key (SMTP & API → SMTP)
3. Add GitHub repo secrets: `BREVO_SMTP_LOGIN` and `BREVO_SMTP_KEY`
   (and `GMAIL_USER` = voiceaifrin1@gmail.com)
Until then, sending is manual from Gmail drafts.

## How the automation works
- `scripts/daily-outreach.js` — finds clinics via Indeed UK RSS (no key),
  filters chains + Scotland, sends initial + 3-day follow-up via Brevo,
  updates pipeline.csv. Signs SENDER_NAME (default "Jordan").
- `scripts/send-drafts.js` — sends all pipeline rows with outcome=`draft-ready`
  via Brevo, marks them `sent`.
- `scripts/generate-report.js` — builds report.html dashboard.
- `.github/workflows/daily-outreach.yml` — runs weekdays 9am UK + on push;
  needs the Brevo secrets to actually send.
- Note: GitHub Actions can fetch job sites fine; THIS chat session's network
  policy blocks fetching arbitrary clinic websites (403 from egress proxy) and
  blocks WebFetch — so manual lead sourcing here relies on WebSearch snippets.

## Gmail MCP quirks learned
- There is NO edit/delete-draft tool. To "change" a draft: trash it
  (`apply_sensitive_thread_label` TRASH by threadId) and `create_draft` anew.
- `list_drafts` sometimes returns `{}` transiently; retry. Use
  `DRAFT_VIEW_METADATA_ONLY` to get ids/threadIds cheaply.

## Other assets
- `CLOSING-PLAYBOOK.md` — paste-ready reply scripts for when a clinic responds.
- `LINKEDIN-OUTREACH.md` — manual LinkedIn DM kit (LinkedIn bans DM automation).
- Buffer LinkedIn posts were scheduled previously (channel id
  6a3c08125ab6d2f106696148).
- Branch: develop on `claude/dental-outreach-agent-setup-6o7vse`; work has been
  pushed to `main` (repo default branch differs).

## Immediate next steps
1. Owner sends the 33 Gmail drafts (verified-email ones first).
2. Owner sets up Brevo secrets → then trigger the workflow for true automation.
3. When a clinic replies, use CLOSING-PLAYBOOK.md to respond and book a call.
4. Keep adding qualified England/Wales/NI leads daily (no Scotland, no chains).
