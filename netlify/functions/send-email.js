// Netlify Function: POST /api/send-email
// Sends an email via Brevo API with open+click tracking enabled.
// Env vars required: BREVO_API_KEY, SENDER_EMAIL (default voiceaifrin1@gmail.com), SENDER_NAME (default Jordan)
// Body: { to, toName, subject, html, contactId }
// Returns: { messageId, success }

export async function handler(event) {
  const cors = {
    'Access-Control-Allow-Origin': '*',
    'Access-Control-Allow-Headers': 'Content-Type',
    'Content-Type': 'application/json',
  };

  if (event.httpMethod === 'OPTIONS') {
    return { statusCode: 200, headers: cors, body: '' };
  }
  if (event.httpMethod !== 'POST') {
    return { statusCode: 405, headers: cors, body: JSON.stringify({ error: 'Method not allowed' }) };
  }

  const apiKey = process.env.BREVO_API_KEY;
  if (!apiKey) {
    return { statusCode: 500, headers: cors, body: JSON.stringify({ error: 'BREVO_API_KEY not configured. Add it in Netlify → Site settings → Environment variables.' }) };
  }

  let body;
  try { body = JSON.parse(event.body); } catch {
    return { statusCode: 400, headers: cors, body: JSON.stringify({ error: 'Invalid JSON body' }) };
  }

  const { to, toName, subject, html, contactId } = body;
  if (!to || !subject || !html) {
    return { statusCode: 400, headers: cors, body: JSON.stringify({ error: 'Missing required fields: to, subject, html' }) };
  }

  const senderEmail = process.env.SENDER_EMAIL || 'voiceaifrin1@gmail.com';
  const senderName = process.env.SENDER_NAME || 'Jordan';

  const payload = {
    sender: { name: senderName, email: senderEmail },
    to: [{ email: to, name: toName || to }],
    subject,
    htmlContent: html,
    trackOpens: 1,
    trackClicks: 1,
    headers: { 'X-Sara-ContactId': String(contactId || '') },
    tags: ['sara-crm', contactId ? `contact-${contactId}` : 'outreach'],
  };

  try {
    const res = await fetch('https://api.brevo.com/v3/smtp/email', {
      method: 'POST',
      headers: { 'api-key': apiKey, 'Content-Type': 'application/json' },
      body: JSON.stringify(payload),
    });
    const data = await res.json();
    if (!res.ok) {
      return { statusCode: res.status, headers: cors, body: JSON.stringify({ error: data.message || 'Brevo API error', details: data }) };
    }
    return { statusCode: 200, headers: cors, body: JSON.stringify({ success: true, messageId: data.messageId }) };
  } catch (err) {
    return { statusCode: 500, headers: cors, body: JSON.stringify({ error: err.message }) };
  }
}
