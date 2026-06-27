// Netlify Function: GET /api/email-stats?contactId=123&tag=contact-123
// Fetches open/click stats from Brevo for a given contact tag.
// Env vars required: BREVO_API_KEY

export async function handler(event) {
  const cors = {
    'Access-Control-Allow-Origin': '*',
    'Access-Control-Allow-Headers': 'Content-Type',
    'Content-Type': 'application/json',
  };

  if (event.httpMethod === 'OPTIONS') {
    return { statusCode: 200, headers: cors, body: '' };
  }

  const apiKey = process.env.BREVO_API_KEY;
  if (!apiKey) {
    return { statusCode: 500, headers: cors, body: JSON.stringify({ error: 'BREVO_API_KEY not configured' }) };
  }

  const { contactId, messageId } = event.queryStringParameters || {};

  try {
    let results = [];

    if (messageId) {
      // Fetch stats for a specific message
      const res = await fetch(`https://api.brevo.com/v3/smtp/emails/${encodeURIComponent(messageId)}`, {
        headers: { 'api-key': apiKey },
      });
      if (res.ok) {
        const data = await res.json();
        results = [data];
      }
    } else if (contactId) {
      // Fetch recent emails by tag
      const tag = `contact-${contactId}`;
      const res = await fetch(
        `https://api.brevo.com/v3/smtp/emails?tags=${encodeURIComponent(tag)}&limit=10&sort=desc`,
        { headers: { 'api-key': apiKey } }
      );
      if (res.ok) {
        const data = await res.json();
        results = data.transactionalEmails || [];
      }
    } else {
      return { statusCode: 400, headers: cors, body: JSON.stringify({ error: 'Provide contactId or messageId' }) };
    }

    // Summarise events
    const summary = results.map(email => ({
      messageId: email.messageId,
      subject: email.subject,
      sentAt: email.date,
      to: email.to?.[0]?.email,
      events: email.events || [],
      opened: (email.events || []).some(e => e.name === 'opened'),
      clicked: (email.events || []).some(e => e.name === 'clicks'),
      bounced: (email.events || []).some(e => e.name === 'hardBounces' || e.name === 'softBounces'),
      unsubscribed: (email.events || []).some(e => e.name === 'unsubscribed'),
    }));

    return { statusCode: 200, headers: cors, body: JSON.stringify({ emails: summary, count: summary.length }) };
  } catch (err) {
    return { statusCode: 500, headers: cors, body: JSON.stringify({ error: err.message }) };
  }
}
