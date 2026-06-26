/**
 * One-shot script: sends all pipeline rows with outcome = 'draft-ready'
 * then marks them 'sent' in pipeline.csv.
 *
 * Sends via Brevo SMTP (free, 300 emails/day, no 2FA required).
 * Requires: BREVO_SMTP_LOGIN and BREVO_SMTP_KEY as env vars / GitHub secrets.
 */

import { readFileSync, writeFileSync, existsSync } from 'fs';
import { parse } from 'csv-parse/sync';
import { stringify } from 'csv-stringify/sync';
import nodemailer from 'nodemailer';

const PIPELINE_FILE  = 'pipeline.csv';
const SENDER_EMAIL   = process.env.GMAIL_USER || 'voiceaifrin1@gmail.com';
const SENDER_NAME    = process.env.SENDER_NAME || 'The Sara team';
const BREVO_LOGIN    = process.env.BREVO_SMTP_LOGIN;
const BREVO_KEY      = process.env.BREVO_SMTP_KEY;
const LANDING_PAGE   = 'https://wonderful-meerkat-938250.netlify.app/';
const DELAY_MS       = 12_000;

if (!BREVO_LOGIN || !BREVO_KEY) {
  console.error('Error: BREVO_SMTP_LOGIN or BREVO_SMTP_KEY is not set.');
  console.error('Add both as GitHub repository secrets.');
  process.exit(1);
}

function createTransport() {
  return nodemailer.createTransport({
    host: 'smtp-relay.brevo.com',
    port: 587,
    secure: false,
    auth: { user: BREVO_LOGIN, pass: BREVO_KEY },
  });
}

function emailBody(clinicName) {
  return `Hi,

Quick question — do you know how many calls ${clinicName} misses in a normal week?

Most practices are surprised when they check. The phone goes while the front desk is busy with someone at the counter, or after you've closed for the day, and the caller doesn't leave a message — they just ring the next dentist on Google. That's new patients gone before you ever speak to them.

That's the problem we solve. We'd set ${clinicName} up so every call gets answered — patients booked straight into your diary, the everyday questions on prices, hours and treatments all handled, day and night. It's automated, so nothing rings out, and it works alongside your team rather than replacing anyone.

Best way to judge it is to ring it yourself and hear a real call:
${LANDING_PAGE}

It's £299 a month and the first month is free, so you can watch it catch the calls you're losing now before paying anything.

Worth a quick listen?

${SENDER_NAME}

If you'd rather not hear from us, just reply STOP and we'll leave it there.`;
}

async function main() {
  if (!existsSync(PIPELINE_FILE)) {
    console.error('pipeline.csv not found'); process.exit(1);
  }

  const raw  = readFileSync(PIPELINE_FILE, 'utf8').trim();
  const rows = parse(raw, { columns: true, skip_empty_lines: true, relax_column_count: true });

  const pending = rows.filter(r => r.outcome === 'draft-ready');
  if (!pending.length) {
    console.log('No draft-ready rows found — nothing to send.'); return;
  }

  console.log(`Sending ${pending.length} email(s) from ${SENDER_EMAIL}…\n`);

  let sent = 0, failed = 0;

  for (const row of pending) {
    const transport = createTransport();
    console.log(`  → ${row.clinic_name} <${row.email}>`);
    try {
      const info = await transport.sendMail({
        from:    `Sara AI <${SENDER_EMAIL}>`,
        to:      row.email,
        subject: 'A quick one about your phones',
        text:    emailBody(row.clinic_name),
      });
      row.outcome   = 'sent';
      row.thread_id = info.messageId || row.thread_id || '';
      row.sent_date = new Date().toISOString().split('T')[0];
      console.log(`     ✓ sent (${info.messageId})`);
      sent++;
    } catch (err) {
      console.error(`     ✗ failed: ${err.message}`);
      failed++;
    }

    if (pending.indexOf(row) < pending.length - 1) {
      process.stdout.write(`     waiting ${DELAY_MS / 1000}s before next…\r`);
      await new Promise(r => setTimeout(r, DELAY_MS));
    }
  }

  const COLUMNS = ['clinic_name', 'email', 'location', 'job_url', 'sent_date', 'thread_id', 'followup_sent', 'reply', 'outcome'];
  writeFileSync(PIPELINE_FILE, COLUMNS.join(',') + '\n' + stringify(rows, { header: false, columns: COLUMNS }));

  console.log(`\nDone. Sent: ${sent}  Failed: ${failed}`);
  console.log('pipeline.csv updated.');
}

main().catch(err => { console.error('Fatal:', err); process.exit(1); });
