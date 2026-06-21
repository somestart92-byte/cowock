# Sara AI — Landing Page Reference

**Live URL:** https://wonderful-meerkat-938250.netlify.app/

> This file is the single source of truth for all email templates and pricing. Always read it before quoting a price or sending a link CTA.

---

## Hero

**Headline:** Your Dental Clinic Needs a Receptionist That Never Sleeps  
**Sub-headline:** Sara AI answers every patient call, books appointments, and handles queries around the clock — no salary, no sick days, no missed calls.

**Primary CTA:** "Get First Month Free" → #get-started section  
**Secondary CTA:** "Hear Sara Live →" → #demo section

---

## Live Voice Demo

Sara is available live at the demo URL above. Visitors can speak to her directly — no signup required.  
When using the link CTA in cold emails, link to the live demo URL.

---

## Stats Bar

| Stat | Value |
|------|-------|
| Call coverage | 24/7 |
| Salary / NI / sick pay | £0 |
| Average answer time | 30 seconds |
| Calls answered | 100% |

---

## Pricing (authoritative)

All plans include a **£999 one-time setup fee**.  
**First month is completely free.** 30-day money-back guarantee after that. Cancel anytime.

| Plan | Monthly | Included |
|------|---------|----------|
| Starter | £197/mo | Up to 200 calls, appointment booking, FAQ handling, call summaries, email support |
| **Growth** (most popular) | **£299/mo** | Unlimited calls, booking + reminders, multilingual, CRM/PMS integration, priority support, monthly report |
| Scale | £497/mo | Unlimited multi-location, custom voice, advanced analytics, dedicated account manager, SLA |

**Default cold-email price to quote:** Growth £299/month + £999 one-time setup.

---

## Guarantee

- First month completely free
- 30-day money-back guarantee
- Cancel any time — no lock-in, no questions

**Use in emails:** "First month is completely free — no risk."

---

## Lead Capture Form

Form name: `sara-leads` (Netlify Forms)  
Notification email: `voiceaifrin1@gmail.com`

### Fields

| Field | Type | Required | Options |
|-------|------|----------|---------|
| Full Name | text | yes | — |
| Email Address | email | yes | — |
| Phone Number | tel | yes | — |
| Service interest | select | yes | 24/7 Call Answering · Appointment Booking · Appointment Reminders · Reducing No-Shows · Replacing / Supporting Receptionist · Full Reception Package |
| Clinic Name | text | no | — |

---

## Key Features Sara Provides

1. **Appointment Booking** — books, reschedules, cancels in real time
2. **Patient Queries** — FAQs, opening hours, pricing, directions
3. **Appointment Reminders** — proactive calls 48 hrs before
4. **Multilingual Support** — serves diverse communities
5. **Call Summaries** — every call logged and summarised
6. **Instant Setup** — live in under 48 hours

---

## Target Market

- Independent UK dental clinics
- Specifically clinics **actively hiring a receptionist** (pain = proven)
- Avoid: NHS trusts, Bupa, Portman, Dental Care Alliance, large chains

---

## Objection Handling

| Objection | Response |
|-----------|----------|
| "Patients won't like talking to a robot" | It's indistinguishable from a real receptionist — hear for yourself on the demo |
| "We already have a receptionist" | Sara handles overflow, out-of-hours, and sick days — not a replacement, an upgrade |
| "What about integration with our software?" | Growth plan includes CRM/PMS integration — we handle the setup |
| "What if it goes wrong?" | First month free, 30-day money-back, cancel anytime — zero risk |

---

## Netlify Forms Setup

To activate lead email notifications:
1. Deploy the site to Netlify
2. Go to **Site → Forms** in the Netlify dashboard
3. Click the `sara-leads` form
4. Go to **Notifications → Add notification → Email notification**
5. Set recipient to `voiceaifrin1@gmail.com`
6. Save

Netlify will then email every lead submission instantly to that address.
