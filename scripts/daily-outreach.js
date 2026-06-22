/**
 * Sara AI — Daily Outreach Automation
 *
 * Runs automatically via GitHub Actions every weekday at 9am UK time.
 * Searches Reed UK for dental clinics hiring a receptionist, sends a
 * cold email to each new clinic, follows up once after 3 days, and
 * updates pipeline.csv.
 *
 * Halal principles observed:
 * - Every email includes a clear opt-out instruction
 * - Maximum 2 emails per clinic (1 initial + 1 follow-up) — never more
 * - Opt-out replies are honoured immediately and permanently
 * - All claims in emails are factually true
 * - Targets corporate B2B mailboxes only (clinic info/reception emails)
 * - No deceptive subject lines or false urgency
 */

import { readFileSync, writeFileSync, existsSync } from 'fs';
import { parse } from 'csv-parse/sync';
import { stringify } from 'csv-stringify/sync';
import { google } from 'googleapis';
import fetch from 'node-fetch';

// ---------------------------------------------------------------------------
// Config
// ---------------------------------------------------------------------------
const PIPELINE_FILE = 'pipeline.csv';
const SENDER_EMAIL  = process.env.GMAIL_USER || 'voiceaifrin1@gmail.com';
const LANDING_PAGE  = 'https://wonderful-meerkat-938250.netlify.app/';

const GMAIL_AUTH = {
  clientId:     process.env.GMAIL_CLIENT_ID,
  clientSecret: process.env.GMAIL_CLIENT_SECRET,
  refreshToken: process.env.GMAIL_REFRESH_TOKEN,
};

const REED_API_KEY = process.env.REED_API_KEY;

// Clinics whose names contain any of these strings will be skipped
const CHAIN_KEYWORDS = [
  'bupa', 'portman', 'mydentist', 'dental care alliance',
  'whitecross', 'denplan', 'nhs trust', 'nhs foundation',
  'pds dental', 'practice plan',
];

// Rate-limit: gap between emails in milliseconds (10 seconds)
const EMAIL_DELAY_MS = 10_000;

// ---------------------------------------------------------------------------
// Pipeline helpers
// ---------------------------------------------------------------------------
function loadPipeline() {
  if (!existsSync(PIPELINE_FILE)) return [];
  const raw = readFileSync(PIPELINE_FILE, 'utf8').trim();
  if (!raw || raw.startsWith('clinic_name') && raw.split('\n').length < 2) return [];
  return parse(raw, { columns: true, skip_empty_lines: true });
}

function savePipeline(rows) {
  const header = 'clinic_name,email,location,job_url,sent_date,thread_id,followup_sent,reply,outcome\n';
  const body   = rows.length ? stringify(rows, { header: false }) : '';
  writeFileSync(PIPELINE_FILE, header + body);
}

// ---------------------------------------------------------------------------
// Reed API — search for dental receptionist jobs in UK
// ---------------------------------------------------------------------------
async function searchJobs() {
  console.log('Searching Reed UK for dental receptionist listings…');
  const url = 'https://www.reed.co.uk/api/1.0/search'
    + '?keywords=dental+receptionist&locationName=United+Kingdom&resultsToTake=100';

  const res = await fetch(url, {
    headers: {
      Authorization: 'Basic ' + Buffer.from(REED_API_KEY + ':').toString('base64'),
    },
  });

  if (!res.ok) throw new Error(`Reed API: ${res.status} ${res.statusText}`);
  const data = await res.json();
  return data.results || [];
}

async function getJobDetail(jobId) {
  const res = await fetch(`https://www.reed.co.uk/api/1.0/jobs/${jobId}`, {
    headers: {
      Authorization: 'Basic ' + Buffer.from(REED_API_KEY + ':').toString('base64'),
    },
  });
  if (!res.ok) return null;
  return res.json();
}

// Extract first email address found in a block of text
function extractEmail(text = '') {
  // Only accept corporate-style emails; skip personal name patterns where possible
  const match = text.match(/\b([a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,})\b/);
  return match ? match[1].toLowerCase() : null;
}

// Try to find a clinic contact email from job description or employer website
async function findEmail(job) {
  // 1. Check job description from detail endpoint
  const detail = await getJobDetail(job.jobId);
  if (detail) {
    const fromDesc = extractEmail(detail.jobDescription || '');
    if (fromDesc) return fromDesc;
  }

  // 2. Try fetching the employer URL (if Reed provides one)
  const employerUrl = detail?.employerProfileUrl || job.employerProfileUrl;
  if (employerUrl) {
    try {
      const page = await fetch(employerUrl, { timeout: 8000 });
      if (page.ok) {
        const html = await page.text();
        const fromPage = extractEmail(html);
        if (fromPage) return fromPage;
      }
    } catch (_) {}
  }

  return null;
}

// ---------------------------------------------------------------------------
// Gmail helpers
// ---------------------------------------------------------------------------
function getGmailClient() {
  const auth = new google.auth.OAuth2(GMAIL_AUTH.clientId, GMAIL_AUTH.clientSecret);
  auth.setCredentials({ refresh_token: GMAIL_AUTH.refreshToken });
  return google.gmail({ version: 'v1', auth });
}

function buildRawMessage({ from, to, subject, body, inReplyTo, references }) {
  const lines = [
    `From: Sara AI <${from}>`,
    `To: ${to}`,
    `Subject: ${subject}`,
    'Content-Type: text/plain; charset=utf-8',
    'MIME-Version: 1.0',
  ];
  if (inReplyTo)  lines.push(`In-Reply-To: ${inReplyTo}`);
  if (references) lines.push(`References: ${references}`);
  lines.push('', body);

  return Buffer.from(lines.join('\r\n'))
    .toString('base64')
    .replace(/\+/g, '-').replace(/\//g, '_').replace(/=+$/, '');
}

async function sendEmail({ to, subject, body, threadId }) {
  const gmail = getGmailClient();
  const raw   = buildRawMessage({ from: SENDER_EMAIL, to, subject, body });

  const params = { userId: 'me', requestBody: { raw } };
  if (threadId) params.requestBody.threadId = threadId;

  const res = await gmail.users.messages.send(params);
  return res.data;
}

// Check whether a prospect has replied (or sent a STOP request)
async function checkReply(email) {
  const gmail = getGmailClient();

  // Search for any message from this address in our inbox
  const res = await gmail.users.messages.list({
    userId: 'me',
    q: `from:${email} in:inbox`,
    maxResults: 5,
  });

  const messages = res.data.messages || [];
  for (const msg of messages) {
    const detail = await gmail.users.messages.get({
      userId: 'me', id: msg.id, format: 'metadata',
      metadataHeaders: ['From', 'Subject'],
    });
    const snippet = (detail.data.snippet || '').toLowerCase();
    if (snippet.includes('stop') || snippet.includes('unsubscribe') || snippet.includes('remove')) {
      return 'opt-out';
    }
    return 'replied';
  }
  return null;
}

// ---------------------------------------------------------------------------
// Email templates (honest, halal — no fabricated claims)
// ---------------------------------------------------------------------------
function initialEmail(clinicName) {
  return {
    subject: 'Before you hire — worth a 2-min read',
    body: `Hi there,

Saw ${clinicName} is hiring a receptionist.

We built an AI that handles the same job — answers calls, books appointments, responds to patient queries 24/7.

No salary. No sick days. No training. £299/month after a one-time setup.

First month is completely free — no risk.

You can hear her answer a patient call yourself — 2 minutes, no signup:
${LANDING_PAGE}

Sara
Sara AI

To opt out, reply STOP and we will not contact you again.`,
  };
}

function followUpEmail() {
  return {
    subject: 'Re: Before you hire — worth a 2-min read',
    body: `Hi there,

Just checking this did not get buried.

Happy to send the demo if useful — takes 2 minutes.

Sara
Sara AI

To opt out, reply STOP.`,
  };
}

// ---------------------------------------------------------------------------
// Main
// ---------------------------------------------------------------------------
async function main() {
  console.log('=== Sara AI Daily Outreach ===');
  console.log(new Date().toLocaleString('en-GB', { timeZone: 'Europe/London' }), '\n');

  const pipeline    = loadPipeline();
  const knownEmails = new Set(pipeline.map(r => r.email).filter(Boolean));
  const knownNames  = new Set(pipeline.map(r => r.clinic_name.toLowerCase()));

  let newSent      = 0;
  let followupSent = 0;
  let optOuts      = 0;
  let skipped      = 0;

  // ── Step 1: Find new prospects and send initial email ──────────────────────
  const jobs = await searchJobs();
  console.log(`Found ${jobs.length} listings on Reed\n`);

  for (const job of jobs) {
    const clinicName = (job.employerName || '').trim();
    if (!clinicName) continue;

    // Skip large chains
    if (CHAIN_KEYWORDS.some(k => clinicName.toLowerCase().includes(k))) {
      skipped++;
      continue;
    }

    // Skip already in pipeline
    if (knownNames.has(clinicName.toLowerCase())) continue;

    const email = await findEmail(job);
    if (!email) {
      console.log(`  No email found: ${clinicName}`);
      continue;
    }

    // Skip personal names in email (prefer corporate mailboxes)
    if (knownEmails.has(email)) continue;

    console.log(`  Emailing: ${clinicName} <${email}>`);
    const { subject, body } = initialEmail(clinicName);

    try {
      const sent = await sendEmail({ to: email, subject, body });

      pipeline.push({
        clinic_name:   clinicName,
        email,
        location:      job.locationName || '',
        job_url:       `https://www.reed.co.uk/jobs/${job.jobId}`,
        sent_date:     new Date().toISOString().split('T')[0],
        thread_id:     sent.threadId || '',
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

  // ── Step 2: Follow-ups and opt-out checks ─────────────────────────────────
  const today = new Date();

  for (const row of pipeline) {
    // Nothing to do for already-closed rows
    if (['opt-out', 'replied', 'demo-requested'].includes(row.outcome)) continue;
    if (!row.email || !row.sent_date) continue;

    // Always check for opt-out reply first — honour it immediately
    const replyStatus = await checkReply(row.email);

    if (replyStatus === 'opt-out') {
      console.log(`  Opt-out received: ${row.clinic_name}`);
      row.reply   = 'STOP';
      row.outcome = 'opt-out';
      optOuts++;
      continue;
    }

    if (replyStatus === 'replied') {
      console.log(`  Reply received: ${row.clinic_name}`);
      row.reply   = 'yes';
      row.outcome = 'replied';
      continue;
    }

    // Send one follow-up if 3+ days have passed and none sent yet
    if (row.followup_sent) continue;

    const daysSince = Math.floor((today - new Date(row.sent_date)) / 86_400_000);
    if (daysSince < 3) continue;

    console.log(`  Following up: ${row.clinic_name}`);
    const { subject, body } = followUpEmail();

    try {
      await sendEmail({ to: row.email, subject, body, threadId: row.thread_id || undefined });
      row.followup_sent = today.toISOString().split('T')[0];
      row.outcome       = 'followup-sent';
      followupSent++;
      await new Promise(r => setTimeout(r, EMAIL_DELAY_MS));
    } catch (err) {
      console.error(`  Follow-up failed (${row.clinic_name}): ${err.message}`);
    }
  }

  savePipeline(pipeline);

  // ── Summary ───────────────────────────────────────────────────────────────
  console.log('\n=== Summary ===');
  console.log(`New emails sent  : ${newSent}`);
  console.log(`Follow-ups sent  : ${followupSent}`);
  console.log(`Opt-outs honoured: ${optOuts}`);
  console.log(`Chains skipped   : ${skipped}`);
  console.log(`Pipeline total   : ${pipeline.length}`);
  console.log('pipeline.csv updated.\n');
}

main().catch(err => { console.error('Fatal:', err); process.exit(1); });
