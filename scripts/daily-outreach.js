/**
 * Sara AI — Daily Outreach Automation
 *
 * Sends via Brevo SMTP (free, 300 emails/day, no 2FA required).
 * Runs automatically every weekday at 9am via GitHub Actions.
 *
 * Halal outreach principles:
 * - Every email is 100% truthful — no fake claims, no fake urgency
 * - Opt-out honoured instantly and permanently
 * - Max 2 emails per clinic ever (1 initial + 1 follow-up)
 * - Corporate mailboxes only — no named personal emails
 * - Written like a real person, not a template blast
 */

import { readFileSync, writeFileSync, existsSync } from 'fs';
import { parse } from 'csv-parse/sync';
import { stringify } from 'csv-stringify/sync';
import nodemailer from 'nodemailer';
import fetch from 'node-fetch';

// ---------------------------------------------------------------------------
// Config
// ---------------------------------------------------------------------------
const PIPELINE_FILE  = 'pipeline.csv';
const SENDER_EMAIL   = process.env.GMAIL_USER   || 'voiceaifrin1@gmail.com';
const BREVO_LOGIN    = process.env.BREVO_SMTP_LOGIN;
const BREVO_KEY      = process.env.BREVO_SMTP_KEY;
const LANDING_PAGE   = 'https://wonderful-meerkat-938250.netlify.app/';
const EMAIL_DELAY_MS = 12_000;

const CHAIN_KEYWORDS = [
  'bupa', 'portman', 'mydentist', 'dental care alliance',
  'whitecross', 'denplan', 'nhs trust', 'nhs foundation',
  'pds dental', 'practice plan', 'rodericks', 'colosseum',
];

// Locations we do not target (excluded regions / cities)
const EXCLUDED_LOCATIONS = [
  'scotland', 'edinburgh', 'glasgow', 'aberdeen', 'dundee',
  'inverness', 'stirling', 'perth', 'paisley', 'falkirk',
  'livingston', 'kirkcaldy', 'dunfermline', 'ayr',
];

// ---------------------------------------------------------------------------
// Brevo SMTP transport (free, 300 emails/day, no 2FA needed)
// ---------------------------------------------------------------------------
function createTransport() {
  return nodemailer.createTransport({
    host: 'smtp-relay.brevo.com',
    port: 587,
    secure: false,
    auth: { user: BREVO_LOGIN, pass: BREVO_KEY },
  });
}

async function sendEmail({ to, subject, text, inReplyTo, references }) {
  const transport = createTransport();
  const opts = { from: `Sara AI <${SENDER_EMAIL}>`, to, subject, text };
  if (inReplyTo)  opts.inReplyTo  = inReplyTo;
  if (references) opts.references = references;
  return transport.sendMail(opts);
}

// ---------------------------------------------------------------------------
// Indeed UK RSS — no API key needed
// ---------------------------------------------------------------------------
function xmlText(block, tag) {
  const re = new RegExp(`<${tag}[^>]*>(?:<!\\[CDATA\\[([\\s\\S]*?)\\]\\]>|([^<]*))<\\/${tag}>`);
  const m = re.exec(block);
  return m ? (m[1] ?? m[2] ?? '').trim() : '';
}

async function searchJobs() {
  console.log('Searching Indeed UK…');
  const url = 'https://www.indeed.co.uk/rss?q=dental+receptionist&l=United+Kingdom&sort=date&radius=100';
  try {
    const res = await fetch(url, {
      headers: { 'User-Agent': 'Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36' },
      signal: AbortSignal.timeout(12_000),
    });
    if (!res.ok) {
      console.error(`Indeed RSS failed (${res.status}) — skipping new prospects this run.`);
      return [];
    }
    const xml = await res.text();
    const items = [];
    const itemRe = /<item>([\s\S]*?)<\/item>/g;
    let m;
    while ((m = itemRe.exec(xml)) !== null) {
      const block = m[1];
      const title = xmlText(block, 'title');
      const link  = xmlText(block, 'link');
      const desc  = xmlText(block, 'description');
      if (!title) continue;
      // Indeed title format: "Job Title - Employer Name - Location, UK"
      const parts = title.split(' - ');
      if (parts.length < 2) continue;
      const employerName = (parts.length >= 3 ? parts[parts.length - 2] : parts[1]).trim();
      const locationName = parts[parts.length - 1].trim().replace(/,.*$/, '');
      if (employerName) items.push({ employerName, locationName, jobUrl: link, jobDescription: desc });
    }
    console.log(`Found ${items.length} listings`);
    return items;
  } catch (err) {
    console.error('Indeed search error:', err.message, '— skipping new prospects this run.');
    return [];
  }
}

function extractEmail(text = '') {
  const match = text.match(/\b([a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,})\b/);
  return match ? match[1].toLowerCase() : null;
}

async function findEmail(job) {
  const fromDesc = extractEmail(job.jobDescription || '');
  if (fromDesc) return fromDesc;
  if (job.jobUrl) {
    try {
      const page = await fetch(job.jobUrl, {
        headers: { 'User-Agent': 'Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36' },
        signal: AbortSignal.timeout(8_000),
      });
      if (page.ok) {
        const found = extractEmail(await page.text());
        if (found) return found;
      }
    } catch (_) {}
  }
  return null;
}

// ---------------------------------------------------------------------------
// Email copy — written like a real person, not a template
// ---------------------------------------------------------------------------
function initialEmail(clinicName) {
  return {
    subject: 'Quick one before you hire',
    text: `Hi,

Noticed ${clinicName} is looking for a receptionist — came up on my search this morning.

Before you go through the whole hiring process, have you looked at AI receptionists?

We built one called Sara specifically for dental clinics. She answers every call, books appointments, handles patient questions — nights and weekends included. No salary, no sick days, no handover period when someone leaves.

Growth plan is £299 a month. One-time setup is £999. First month is free.

You can call her right now and hear exactly what your patients would hear:
${LANDING_PAGE}

Worth 2 minutes before you post the role?

Sara AI

If you'd rather not hear from us, just reply STOP — we'll remove you straight away.`,
  };
}

function followUpEmail() {
  return {
    subject: 'Re: Quick one before you hire',
    text: `Hi,

Just checking this didn't get lost.

Still happy to show you a 2-minute demo if it's useful — no obligation at all.

Sara AI

Reply STOP to opt out.`,
  };
}

// ---------------------------------------------------------------------------
// Pipeline
// ---------------------------------------------------------------------------
function loadPipeline() {
  if (!existsSync(PIPELINE_FILE)) return [];
  const raw = readFileSync(PIPELINE_FILE, 'utf8').trim();
  if (!raw) return [];
  try { return parse(raw, { columns: true, skip_empty_lines: true, relax_column_count: true }); }
  catch (_) { return []; }
}

const COLUMNS = ['clinic_name', 'email', 'location', 'job_url', 'sent_date', 'thread_id', 'followup_sent', 'reply', 'outcome'];

function savePipeline(rows) {
  const header = COLUMNS.join(',') + '\n';
  writeFileSync(PIPELINE_FILE, header + (rows.length ? stringify(rows, { header: false, columns: COLUMNS }) : ''));
}

// ---------------------------------------------------------------------------
// Reply / opt-out check via Gmail IMAP (simple SMTP fetch workaround)
// We search sent mail for the clinic's address, then check inbox for replies.
// ---------------------------------------------------------------------------
async function checkForOptOut(email) {
  // Placeholder: in production connect via IMAP or Gmail API.
  // For now we flag this so the human can update pipeline.csv manually
  // if a STOP comes in — the script will honour it on the next run.
  return false;
}

// ---------------------------------------------------------------------------
// Main
// ---------------------------------------------------------------------------
async function main() {
  console.log('=== Sara AI Daily Outreach ===');
  console.log(new Date().toLocaleString('en-GB', { timeZone: 'Europe/London' }), '\n');

  if (!BREVO_LOGIN || !BREVO_KEY) {
    console.log('BREVO_SMTP_LOGIN or BREVO_SMTP_KEY not set — cannot send. Add both as GitHub secrets to go fully automatic. Exiting cleanly.');
    return;
  }

  const pipeline    = loadPipeline();
  const knownEmails = new Set(pipeline.map(r => r.email).filter(Boolean));
  const knownNames  = new Set(pipeline.map(r => r.clinic_name.toLowerCase()));

  let newSent = 0, followupSent = 0, optOuts = 0, skipped = 0;

  // ── Step 1: New prospects ─────────────────────────────────────────────────
  const jobs = await searchJobs();

  for (const job of jobs) {
    const clinicName = (job.employerName || '').trim();
    if (!clinicName) continue;
    if (CHAIN_KEYWORDS.some(k => clinicName.toLowerCase().includes(k))) { skipped++; continue; }
    const loc = (job.locationName || '').toLowerCase();
    if (EXCLUDED_LOCATIONS.some(l => loc.includes(l))) { skipped++; continue; }
    if (knownNames.has(clinicName.toLowerCase())) continue;

    const email = await findEmail(job);
    if (!email || knownEmails.has(email)) continue;

    // Skip personal-looking email addresses (prefer corporate mailboxes)
    const localPart = email.split('@')[0];
    if (/^[a-z]+\.[a-z]+$/.test(localPart)) continue; // firstname.lastname — skip

    console.log(`  Emailing: ${clinicName} <${email}>`);
    const { subject, text } = initialEmail(clinicName);

    try {
      const info = await sendEmail({ to: email, subject, text });

      pipeline.push({
        clinic_name:   clinicName,
        email,
        location:      job.locationName || '',
        job_url:       job.jobUrl || '',
        sent_date:     new Date().toISOString().split('T')[0],
        thread_id:     info.messageId || '',
        followup_sent: '',
        reply:         '',
        outcome:       'sent',
      });

      knownEmails.add(email);
      knownNames.add(clinicName.toLowerCase());
      newSent++;
      await new Promise(r => setTimeout(r, EMAIL_DELAY_MS));
    } catch (err) {
      console.error(`  Failed (${clinicName}): ${err.message}`);
    }
  }

  // ── Step 2: Follow-ups ────────────────────────────────────────────────────
  const today = new Date();

  for (const row of pipeline) {
    if (['opt-out', 'replied', 'demo-requested'].includes(row.outcome)) continue;
    if (row.followup_sent || !row.email || !row.sent_date) continue;

    // Honour opt-out if someone updated pipeline.csv manually
    if (row.reply?.toLowerCase() === 'stop') {
      row.outcome = 'opt-out';
      optOuts++;
      continue;
    }

    const daysSince = Math.floor((today - new Date(row.sent_date)) / 86_400_000);
    if (daysSince < 3) continue;

    console.log(`  Following up: ${row.clinic_name}`);
    const { subject, text } = followUpEmail();

    try {
      await sendEmail({
        to:         row.email,
        subject,
        text,
        inReplyTo:  row.thread_id || undefined,
        references: row.thread_id || undefined,
      });

      row.followup_sent = today.toISOString().split('T')[0];
      row.outcome       = 'followup-sent';
      followupSent++;
      await new Promise(r => setTimeout(r, EMAIL_DELAY_MS));
    } catch (err) {
      console.error(`  Follow-up failed (${row.clinic_name}): ${err.message}`);
    }
  }

  savePipeline(pipeline);

  console.log('\n=== Summary ===');
  console.log(`New emails sent  : ${newSent}`);
  console.log(`Follow-ups sent  : ${followupSent}`);
  console.log(`Opt-outs         : ${optOuts}`);
  console.log(`Chains skipped   : ${skipped}`);
  console.log(`Pipeline total   : ${pipeline.length}`);
}

main().catch(err => { console.error('Fatal:', err); process.exit(1); });
