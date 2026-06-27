// Netlify Function: POST /api/send-email
// Proxies to your Google Apps Script Web App which sends via Gmail.
// Required env var: GAS_WEB_APP_URL  (from script.google.com deploy)
// Optional env vars: SENDER_NAME (default Jordan)
// Body: { to, toName, subject, html, contactId, clinicName }
// Returns: { success, messageId }

export async function handler(event) {
  const cors = {
    'Access-Control-Allow-Origin': '*',
    'Access-Control-Allow-Headers': 'Content-Type',
    'Content-Type': 'application/json',
  };

  if (event.httpMethod === 'OPTIONS') return { statusCode: 200, headers: cors, body: '' };
  if (event.httpMethod !== 'POST') return { statusCode: 405, headers: cors, body: JSON.stringify({ error: 'POST only' }) };

  const gasUrl = process.env.GAS_WEB_APP_URL;
  if (!gasUrl) {
    return {
      statusCode: 500, headers: cors,
      body: JSON.stringify({
        error: 'GAS_WEB_APP_URL not set. Deploy the Google Apps Script (gas/Code.gs) and add the URL to Netlify env vars.',
        setup: true,
      }),
    };
  }

  let body;
  try { body = JSON.parse(event.body); }
  catch { return { statusCode: 400, headers: cors, body: JSON.stringify({ error: 'Invalid JSON' }) }; }

  const { to, toName, subject, html, contactId, clinicName } = body;
  if (!to || !subject || !html) {
    return { statusCode: 400, headers: cors, body: JSON.stringify({ error: 'Missing: to, subject, html' }) };
  }

  try {
    const res = await fetch(gasUrl, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ to, toName, subject, html, contactId, clinicName, gasUrl }),
      redirect: 'follow',
    });
    const text = await res.text();
    let data;
    try { data = JSON.parse(text); } catch { data = { raw: text }; }

    if (data.error) return { statusCode: 500, headers: cors, body: JSON.stringify(data) };
    return { statusCode: 200, headers: cors, body: JSON.stringify(data) };
  } catch (err) {
    return { statusCode: 500, headers: cors, body: JSON.stringify({ error: err.message }) };
  }
}
