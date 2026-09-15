# Cold outreach sequence — local service businesses

Three emails over seven days. Plain text on purpose: no HTML, no images, no
tracking pixel, and no link in the first email. Cold mail that looks like
marketing gets filtered like marketing.

Merge fields to fill in per prospect: `{{first_name}}`, `{{company}}`,
`{{city}}`, `{{trade}}`. Yours, once: `{{sender_name}}`, `{{demo_number}}`,
`{{postal_address}}`.

> **Truthfulness note.** The strongest opener in cold email is a real
> observation — "I called Tuesday at 6pm and got voicemail." Only use it if you
> actually called. The default below makes no claim you cannot back up, which is
> both the halal_rules requirement and the safer sales position: an owner who
> checks the call log and finds you lied is gone for good.

---

## Email 1 — day 0

**Subject:** your phone line after hours

```
Hi {{first_name}},

Quick one - when a call comes into {{company}} while you're on a job or
after close, what happens to it right now?

I build AI receptionists for {{trade}} shops around {{city}}. It answers
when you can't, tells the caller in the first sentence that it's an AI,
takes a name and number, and can book into your calendar.

Want me to send a 30-second recording of what your callers would hear?

{{sender_name}}

--
Reply "stop" and I won't email again.
{{postal_address}}
```

## Email 2 — day 3

**Subject:** re: your phone line after hours

```
Hi {{first_name}},

Following up once.

The part most {{trade}} owners care about isn't the AI - it's that the 7pm
call doesn't go to the next shop on the list.

What it won't do: handle an upset customer, or anything complicated. Those
it takes a message for and flags so you can call back. That's the honest
limit of it.

Still happy to send that recording if you want to hear it.

{{sender_name}}

--
Reply "stop" and I won't email again.
{{postal_address}}
```

## Email 3 — day 7

**Subject:** closing the loop

```
Hi {{first_name}},

Last one from me.

If after-hours calls aren't a problem worth solving at {{company}} right
now, no worries - I'll leave it there.

If they are, the demo line is {{demo_number}}. Call it and talk to it
yourself. No form, no signup.

{{sender_name}}

--
Reply "stop" and I won't email again.
{{postal_address}}
```

---

## Rules for sending these

1. **Separate domain.** Send from `getvoicedeskai.com`, never the domain your
   paying customers' email arrives from. If deliverability tanks, it takes the
   sending domain's reputation with it.
2. **Set up SPF, DKIM and DMARC** on that domain before the first send, and warm
   it up: 5–10 mails a day for two weeks before going higher.
3. **20–40 a day, maximum**, sent over hours rather than in one burst.
4. **Stop the sequence the moment someone replies.** Following up on a person
   who already answered is the fastest way to lose them.
5. **Reply to every reply within the hour** if you can. Speed is most of the
   advantage a small operator has.
6. **Honor "stop" immediately** — it is the law (CAN-SPAM) and the thing that
   keeps you out of spam folders.

## Legal shape (US, business-to-business)

CAN-SPAM permits unsolicited commercial email to businesses provided the From
and Subject are honest, there is a working opt-out, and your physical postal
address is in the message. All three are in the templates above. The EU, UK and
Canada require consent first — these templates are not lawful there.
