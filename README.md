# Sara AI — Automated Outreach for UK Dental Clinics

AI voice receptionist for dental clinics. This repo runs the whole business:
landing page + fully automated cold outreach to clinics that are actively
hiring a receptionist.

**Live demo / landing page:** https://wonderful-meerkat-938250.netlify.app/

---

## How it runs itself

Every weekday at 9am UK time, GitHub Actions (`.github/workflows/daily-outreach.yml`):

1. **Sends any ready drafts** — pipeline rows marked `draft-ready` (`scripts/send-drafts.js`)
2. **Finds new clinics** hiring receptionists via the Reed UK API, emails each one (`scripts/daily-outreach.js`)
3. **Follows up** once after 3 days on anyone who hasn't replied
4. **Rebuilds the dashboard** (`scripts/generate-report.js` → `report.html`)
5. **Commits** the updated pipeline + report back to the repo

All outreach is **halal**: every claim is true, every email has an opt-out,
max 2 emails per clinic ever, corporate mailboxes only, written like a real person.

---

## One-time setup (≈5 minutes)

### 1. Make this the default branch
GitHub → **Settings → Branches → Default branch** → switch to `main`.
(Scheduled workflows only run from the default branch.)

### 2. Add two repository secrets
GitHub → **Settings → Secrets and variables → Actions → New repository secret**:

| Secret | Value |
|--------|-------|
| `GMAIL_APP_PASSWORD` | 16-char App Password from myaccount.google.com → Security → App passwords |
| `GMAIL_USER` | `voiceaifrin1@gmail.com` |

New prospects are found automatically via Indeed UK — no API key needed.

### 3. Run it
GitHub → **Actions → Daily Outreach → Run workflow** (or wait for 9am).

That's it. After this, the business runs hands-free. You only step in when a
clinic replies — update `reply` and `outcome` in `pipeline.csv`.

---

## Pipeline

`pipeline.csv` is the single source of truth. Columns:

```
clinic_name,email,location,job_url,sent_date,thread_id,followup_sent,reply,outcome
```

Outcomes: `draft-ready` · `sent` · `followup-sent` · `replied` · `demo-requested` · `opt-out` · `no-reply`

Open `report.html` in a browser for the visual dashboard (KPIs + charts).
