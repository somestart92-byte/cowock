# Setup Guide — Buffer Publishing & Analytics

The cowock agent can create everything (products, PDFs, graphics, marketing) on
its own. But two things only **you** can do, because of how account security
works: **grant tool permissions** and **connect social accounts**. This guide is
the one-time checklist.

> Why can't the agent do these itself? By design. An AI granting itself
> permission to auto-publish, or logging into your social accounts, would defeat
> the safety model. The agent does the work; you hold the keys.

---

## 1. Activate Buffer permissions (fixes "MCP tool call requires approval")

Every Buffer action (posting, analytics, even reads) is gated until you allow it.

**Option A — settings file (recommended, durable):**
1. Rename the sample file:
   `.claude/settings.sample.json`  →  `.claude/settings.json`
2. **Start a new Claude Code session** on this branch
   (`claude/halal-business-agent-vwge5z`). Permission rules load at session
   start, so the running session won't pick them up — a fresh one will.

**Option B — slash command:**
- In your client run `/permissions` → **Add rule → Allow** → enter `mcp__Buffer__*`

The rule that needs allowing:
```json
{
  "permissions": {
    "allow": [
      "mcp__Buffer__create_post",
      "mcp__Buffer__get_account",
      "mcp__Buffer__list_channels",
      "mcp__Buffer__get_channel",
      "mcp__Buffer__list_posts",
      "mcp__Buffer__get_post",
      "mcp__Buffer__get_aggregated_post_metrics"
    ]
  }
}
```

---

## 2. Connect / reconnect channels (at publish.buffer.com)

| Channel | Service | Status | Action |
|---|---|---|---|
| digitally70 | Pinterest | ✅ connected | none |
| somestart92 | Threads | ✅ connected | none |
| momsguide1 | TikTok | ⚠️ disconnected | reconnect |
| — | Instagram | ❌ not connected | connect (if you want IG posts) |

These are OAuth logins — do them in the Buffer web app. No agent tool can.

Notes:
- **Pinterest & TikTok need an image/video** to post; the agent hosts images via
  a public GitHub raw URL automatically (see `PLAYBOOK.md`).
- **Threads is text-only** and posts on automatic scheduling.

---

## 3. Verify (in a fresh session)

Say any of these — they should run with no permission prompts:
- "Post the Screen-Free Vault to Threads"
- "Queue the vault pin to Pinterest"
- "Pull my Buffer analytics and analyze them"

---

## Known IDs (for speed)

- **Organization:** `699762013a9af5175fc030e9` (My Organization, tz Africa/Cairo)
- **Pinterest** digitally70: channel `6997b6fdd6f8d304f9314495`
  - Board "Printables for Moms": serviceId `1147855092467343753`
- **Threads** somestart92: channel `6a2afec438b55793458600f1`
- **TikTok** momsguide1: channel `69b37be37be9f8b1714ec9a4` (reconnect first)

---

## What's already done (no action needed)
- Products, PDFs, graphics, marketing copy, market research, analytics module —
  all built and committed.
- One Threads post is already queued from an earlier session.

## What still needs you
- Steps 1 & 2 above (permissions + channels).
- Anything involving **money** (store setup, payouts) — always human.
