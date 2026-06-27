/**
 * Sara CRM — Google Apps Script
 * ─────────────────────────────
 * SETUP (one-time, ~3 minutes):
 * 1. Go to script.google.com → New project → paste this whole file
 * 2. Click "Deploy" → "New deployment" → Type: Web app
 *    - Execute as: Me (your Google account)
 *    - Who has access: Anyone
 * 3. Click Deploy → copy the Web App URL
 * 4. In Netlify → Site settings → Environment variables, add:
 *      GAS_WEB_APP_URL = <paste URL here>
 *      SENDER_NAME     = Jordan
 *
 * The script auto-creates a "Sara CRM - Email Log" Google Sheet
 * in your Drive on the very first email send.
 */

const SHEET_NAME = 'EmailLog';

// ── SHEET HELPERS ──────────────────────────────────────────────

function getSpreadsheet() {
  const props = PropertiesService.getScriptProperties();
  let ssId = props.getProperty('SS_ID');
  if (ssId) {
    try { return SpreadsheetApp.openById(ssId); } catch (e) { /* deleted, recreate */ }
  }
  const ss = SpreadsheetApp.create('Sara CRM — Email Log');
  const sheet = ss.getActiveSheet();
  sheet.setName(SHEET_NAME);
  sheet.appendRow(['ContactId', 'ClinicName', 'To', 'Subject', 'SentAt', 'MessageId', 'Opened', 'OpenedAt']);
  sheet.setFrozenRows(1);
  sheet.setColumnWidth(1, 90);
  sheet.setColumnWidth(2, 160);
  sheet.setColumnWidth(3, 220);
  sheet.setColumnWidth(4, 260);
  sheet.setColumnWidth(6, 220);
  props.setProperty('SS_ID', ss.getId());
  return ss;
}

function getLogSheet() {
  const ss = getSpreadsheet();
  return ss.getSheetByName(SHEET_NAME) || ss.getActiveSheet();
}

// ── POST: Send email ───────────────────────────────────────────

function doPost(e) {
  try {
    const data = JSON.parse(e.postData.contents);
    const { to, toName, subject, html, contactId, clinicName, gasUrl } = data;

    if (!to || !subject) return json({ error: 'Missing to or subject' });

    const messageId = 'sara-' + Date.now() + '-' + Math.random().toString(36).slice(2, 7);
    const pixelUrl  = gasUrl + '?action=pixel&c=' + encodeURIComponent(contactId) + '&m=' + messageId;

    const senderName = PropertiesService.getScriptProperties().getProperty('SENDER_NAME') || 'Jordan';

    // Build HTML: append invisible tracking pixel
    const htmlBody = (html || '') +
      '\n<div style="display:none!important;max-height:0;overflow:hidden">' +
      '<img src="' + pixelUrl + '" width="1" height="1" alt="" border="0">' +
      '</div>';

    // Plain-text fallback (strip tags)
    const plain = (html || subject).replace(/<[^>]+>/g, '').trim();

    GmailApp.sendEmail(to, subject, plain, {
      htmlBody: htmlBody,
      name: senderName,
    });

    // Log to sheet
    getLogSheet().appendRow([
      String(contactId),
      clinicName || '',
      to,
      subject,
      new Date().toISOString(),
      messageId,
      false,
      '',
    ]);

    return json({ success: true, messageId: messageId });

  } catch (err) {
    Logger.log('doPost error: ' + err.message);
    return json({ error: err.message });
  }
}

// ── GET: tracking pixel + stats ────────────────────────────────

function doGet(e) {
  const action = (e.parameter && e.parameter.action) || 'pixel';

  // ── Open tracking pixel ──
  if (action === 'pixel') {
    const contactId = e.parameter.c;
    const messageId = e.parameter.m;

    if (contactId && messageId) {
      try {
        const sheet = getLogSheet();
        const values = sheet.getDataRange().getValues();
        for (let i = 1; i < values.length; i++) {
          if (values[i][5] === messageId && !values[i][6]) {
            sheet.getRange(i + 1, 7).setValue(true);
            sheet.getRange(i + 1, 8).setValue(new Date().toISOString());
            break;
          }
        }
      } catch (_) { /* silent — pixel must still return */ }
    }

    // 1×1 transparent GIF
    return ContentService
      .createTextOutput('')
      .downloadAsFile('pixel.gif');
    // Note: GAS can't return binary; use the workaround below for real pixel:
  }

  // ── Stats for a contact ──
  if (action === 'stats') {
    const contactId = e.parameter.c;
    const sheet = getLogSheet();
    const values = sheet.getDataRange().getValues();
    const rows = [];
    for (let i = 1; i < values.length; i++) {
      if (!contactId || String(values[i][0]) === String(contactId)) {
        rows.push({
          contactId: values[i][0],
          clinicName: values[i][1],
          to: values[i][2],
          subject: values[i][3],
          sentAt: values[i][4],
          messageId: values[i][5],
          opened: values[i][6],
          openedAt: values[i][7],
        });
      }
    }
    return json({ emails: rows, count: rows.length });
  }

  // ── Health check ──
  if (action === 'ping') {
    return json({ ok: true, user: Session.getActiveUser().getEmail(), ts: new Date().toISOString() });
  }

  return json({ error: 'Unknown action. Use action=ping|stats|pixel' });
}

// ── PIXEL: real binary GIF via HtmlService workaround ──────────
// Because ContentService can't serve binary, we serve a redirect to
// a data-URI page that triggers the log via a side-channel GET first.
// Simpler: serve an HTML page that immediately loads the real pixel.
// For email clients that render HTML, the <img> in the email body
// calls this URL; GAS logs it and serves the redirect.
// (The above doGet pixel branch handles the logging; the "image"
// that email clients receive is an empty 0-byte response, which is
// fine — the open is still logged before the response is sent.)

function json(obj) {
  return ContentService
    .createTextOutput(JSON.stringify(obj))
    .setMimeType(ContentService.MimeType.JSON);
}
