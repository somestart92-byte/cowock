# Dispatch — landing page

Offer page for an AI front desk aimed at home-service businesses (HVAC, plumbing,
electrical, roofing). Modeled on the Atlas offer structure, written to the
truthful-marketing rules in `config.yaml → halal_rules`: no income claims, no
guarantees, no fabricated testimonials, "can/should" instead of "will".

## Files

- `index.html` — the whole page. Single file, no build step, no dependencies
  except Google Fonts (Archivo, IBM Plex Sans, IBM Plex Mono).

## The live demo

The page links to an ElevenLabs conversational agent playing the after-hours
intake specialist for a fictional HVAC company.

- Agent: `Dispatch Demo - Northside Heating and Air`
- Agent ID: `agent_8901m2mzwfhgeecbayjmgdnqkedw`
- Hosted demo: https://elevenlabs.io/app/talk-to?agent_id=agent_8901m2mzwfhgeecbayjmgdnqkedw

The page currently **links out** to that hosted page rather than embedding the
widget, because the Artifact hosting sandbox blocks the WebSocket connection the
widget needs. When you host this on your own domain there is no such
restriction — swap the link buttons for the inline widget:

```html
<elevenlabs-convai agent-id="agent_8901m2mzwfhgeecbayjmgdnqkedw"></elevenlabs-convai>
<script src="https://unpkg.com/@elevenlabs/convai-widget-embed" async type="text/javascript"></script>
```

Before going live on a public domain, turn on the agent's allowlist
(`platform_settings.auth.allowlist`) so only your domain can start conversations
against it, or the agent ID in your page source is an open tab on your account.

## Before this goes in front of anyone

1. **Booking link.** `#REPLACE-WITH-YOUR-BOOKING-LINK` in the closing section —
   point it at your calendar.
2. **Brand name.** "Dispatch" appears in the `<title>`, the header logo, the body
   copy and the footer. Check the name is clear for your market before printing it
   on anything.
3. **Voice.** The demo uses the workspace default conversational voice. A warmer
   receptionist voice (e.g. "Real AI Receptionist Kai", `gh9yOzacZabdERF6GI7O`)
   has to be added to the workspace before it can be assigned to the agent.
4. **Pricing.** The page deliberately shows no price and routes to a call, per the
   brief. The FAQ describes the shape (build fee + monthly) without a number.

## Demo agent regression test

A simulation test is attached to the workspace and covers a stressed after-hours
caller who asks the price, pushes back on the diagnostic fee, asks for a same-night
visit, and challenges whether they're talking to a human.

- Test ID: `test_1801m2mzztsfemxvb0aejxtjr04b`

Re-run it after any change to the agent prompt. It checks seven things, including
that the agent admits it is an AI when asked, offers two concrete windows rather
than "when works for you", reads the callback number back, and never promises a
specific repair, technician or part.
