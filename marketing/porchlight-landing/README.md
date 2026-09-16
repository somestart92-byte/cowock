# Porchlight — landing page

Offer page for an AI front desk aimed at residential home-service businesses
across four trades: HVAC, plumbing, electrical and roofing.

Written to the truthful-marketing rules in `config.yaml → halal_rules`: no income
claims, no guarantees, no fabricated testimonials, "can/should" instead of "will".

## Deliberately not a copy of Atlas

The category is the same; the framing is ours.

- **No performance guarantee.** Atlas promises "if we don't deliver, you don't
  pay." That's a financial promise about an outcome we can't control, and the
  repo rules forbid guarantees. Not used.
- **No "live in 14 days."** The install sequence is gated on the customer's
  approval, not a day count. The page says three to five weeks and names the
  variable honestly (phone system access, and how long the customer wants to
  spend trying to break it).
- **Organized by when a lead goes cold, not by channel.** Atlas splits by
  product surface (voice / iMessage / outbound). This page splits by the gap
  being covered: after the last truck, the overnight form, the estimate that
  went quiet. Same capabilities, different argument.
- **Proof is a call log, not testimonials.** A before/after inbound log,
  labeled as an illustration. No invented customer quotes.

## Files

- `index.html` — the whole page. Single file, no build step, no dependencies
  except Google Fonts (Archivo, IBM Plex Sans, IBM Plex Mono).

## The live demo

An ElevenLabs conversational agent playing after-hours intake for a fictional
four-trade company.

- Agent: `Porchlight Demo - Ridgeway Home Services` (persona: Wren)
- Agent ID: `agent_8901m2mzwfhgeecbayjmgdnqkedw`
- Hosted demo: https://elevenlabs.io/app/talk-to?agent_id=agent_8901m2mzwfhgeecbayjmgdnqkedw

It identifies the trade from the caller's first sentence, runs trade-specific
triage, quotes that trade's own fee ($89 HVAC diagnostic / $79 plumbing service
call / $99 electrical diagnostic / free roofing estimate), escalates the
dangerous cases, and refers out what Ridgeway doesn't do.

The page currently **links out** to the hosted page rather than embedding the
widget, because the Artifact hosting sandbox blocks the WebSocket the widget
needs. On your own domain there is no such restriction — swap the link buttons
for the inline widget:

```html
<elevenlabs-convai agent-id="agent_8901m2mzwfhgeecbayjmgdnqkedw"></elevenlabs-convai>
<script src="https://unpkg.com/@elevenlabs/convai-widget-embed" async type="text/javascript"></script>
```

Before going live on a public domain, turn on the agent's allowlist
(`platform_settings.auth.allowlist`) so only your domain can start conversations
against it. The agent ID sits in your page source; without the allowlist it is an
open tab on your ElevenLabs account.

## Before this goes in front of anyone

1. **Booking link.** `#REPLACE-WITH-YOUR-BOOKING-LINK` in the closing section —
   point it at your calendar.
2. **Brand name.** "Porchlight" appears in the `<title>`, the header, the body
   copy and the footer. Check it's clear in your market before printing it.
3. **Voice.** The demo uses the workspace default conversational voice. A warmer
   receptionist voice (e.g. "Real AI Receptionist Kai", `gh9yOzacZabdERF6GI7O`)
   must be added to the workspace before it can be assigned.
4. **Pricing.** The page shows no number and routes to a call, per the brief. The
   FAQ describes the shape (build fee + monthly) without committing to a figure.
5. **The four fees are invented** for the demo. Replace them with the real ones
   when you build this for an actual shop.

## Demo agent regression tests

One simulation per trade, each written to be adversarial rather than a happy path.

| Trade | Test ID | What it stresses |
|---|---|---|
| HVAC | `test_0901m2n0se2qf70v9hw0pk6yz61k` | Price question before details; pushback on the fee; "are you a real person?"; refuses to guess the after-hours fee |
| Plumbing | `test_0901m2n0nxm1ecstefz6395zwjdd` | Active flooding; must tell the caller to shut the water off *before* booking; correct trade fee |
| Electrical | `test_4101m2n0p9xaf9paw4r87095d210` | Caller withholds the burning smell; agent must ask, then escalate; must never coach a panel repair |
| Roofing | `test_2601m2n0s2y9fg9vrhjf7x6kh3s1` | Storm damage; water near a ceiling light; insurance question it must not answer; gate/dog check |

Re-run all four after any change to the agent prompt.

**Known failure this caught:** the first roofing run asked how close the water was
to the ceiling light, got an answer, and replied "Okay, that helps" — then moved
on without acting on it. The prompt now carries a `CLOSE THE LOOP ON EVERY SAFETY
QUESTION` rule: a safety question that gets asked must be resolved out loud,
either by escalating or by naming the precaution that still applies.
